"""独立接口自动化场景编排存储与管理 API。

与普通单接口「用例管理库」(/api/v1/cases) 完全解耦，独立存储于自动化场景库中。
"""

from __future__ import annotations

import json
import logging
import re
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import assert_project_access, get_current_user
from app.core.config import settings
from app.core.database import get_db
from app.models.user import User, UserRole
from app.models.user_project import ProjectRole
from app.models.case import CaseType, TestCase
from app.models.project import Module
from app.services.spec_sync import case_request_fingerprint

from app.services.workflow_dag_engine import (
    WorkflowDagError,
    execute_workflow_dag,
    validate_and_toposort_workflow,
)
from app.services.workflow_dataflow_validator import (
    WorkflowDataflowError,
    validate_workflow_dataflow_topology,
)
from app.services.workflow_debugger import (
    WorkflowDebuggerError,
    create_debug_session,
    get_debug_session,
    resume_debug_session,
    step_debug_session,
    stop_debug_session,
)

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/api-scenarios",
    tags=["接口自动化场景"],
    dependencies=[Depends(get_current_user)],
)

_LOCK = threading.Lock()


def _store_path() -> Path:
    base = settings.LOCAL_DATA_PATH
    base.mkdir(parents=True, exist_ok=True)
    return base / "api_scenarios.json"


def _load_all() -> list[dict[str, Any]]:
    path = _store_path()
    if not path.exists():
        return []
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
        return raw if isinstance(raw, list) else []
    except Exception:
        logger.exception("加载 api_scenarios.json 失败")
        try:
            if path.stat().st_size > 0:
                corrupted_bak = path.with_suffix(".corrupted")
                path.rename(corrupted_bak)
                logger.warning("已将异常场景文件备份至 %s", corrupted_bak)
        except Exception:
            pass
        return []


def _save_all(items: list[dict[str, Any]]) -> None:
    path = _store_path()
    tmp_path = path.with_suffix(".tmp")
    tmp_path.write_text(json.dumps(items, ensure_ascii=False, indent=2), encoding="utf-8")
    tmp_path.replace(path)


def read_project_scenarios_snapshot(project_id: int) -> list[dict[str, Any]]:
    """Read a project snapshot without writes; callers must enforce project access first."""
    path = settings.LOCAL_DATA_PATH / "api_scenarios.json"
    if not path.exists():
        return []
    try:
        with _LOCK:
            raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise HTTPException(status_code=503, detail="场景数据暂时不可读取，无法计算影响面") from exc
    if not isinstance(raw, list):
        raise HTTPException(status_code=503, detail="场景数据格式异常，无法计算影响面")
    return [item for item in raw if isinstance(item, dict) and item.get("project_id") == project_id]


class ApiScenarioSaveIn(BaseModel):
    project_id: int
    module_id: int | None = None
    name: str = Field(..., min_length=1, max_length=200)
    description: str = ""
    env_id: int | None = None
    steps: list[dict[str, Any]] = Field(default_factory=list)


class ApiScenarioRunRecordIn(BaseModel):
    status: str = "passed"
    duration_ms: int = 0


async def _bind_source_cases(
    db: AsyncSession, project_id: int, steps: list[dict[str, Any]], *, preserve_existing: bool = False
) -> list[dict[str, Any]]:
    source_ids = {
        step.get("sourceCaseId")
        for step in steps
        if isinstance(step.get("sourceCaseId"), int) and not isinstance(step.get("sourceCaseId"), bool)
    }
    if not source_ids:
        return steps
    result = await db.execute(
        select(TestCase)
        .join(Module, TestCase.module_id == Module.id)
        .where(Module.project_id == project_id, TestCase.case_type == CaseType.api, TestCase.id.in_(source_ids))
    )
    sources = {case.id: case for case in result.scalars().all()}
    bound_steps = []
    for step in steps:
        bound = dict(step)
        source = sources.get(step.get("sourceCaseId"))
        fingerprint = step.get("sourceCaseFingerprint")
        if source is None:
            bound.pop("sourceCaseFingerprint", None)
        elif not preserve_existing or not (isinstance(fingerprint, str) and re.fullmatch(r"[0-9a-f]{64}", fingerprint)):
            bound["sourceCaseFingerprint"] = case_request_fingerprint(source)
        bound_steps.append(bound)
    return bound_steps


@router.get("")
async def list_api_scenarios(
    project_id: int | None = Query(default=None),
    module_id: int | None = Query(default=None),
    keyword: str | None = Query(default=None),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    if project_id is not None:
        await assert_project_access(db, current_user, project_id, ProjectRole.viewer)
    elif current_user.role != UserRole.admin:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="project_id is required")

    with _LOCK:
        items = _load_all()
    if project_id is not None:
        items = [s for s in items if s.get("project_id") == project_id]
    if module_id is not None:
        items = [s for s in items if s.get("module_id") == module_id]
    if keyword and keyword.strip():
        kw = keyword.strip().lower()
        items = [
            s for s in items if kw in str(s.get("name", "")).lower() or kw in str(s.get("scenario_code", "")).lower()
        ]
    items.sort(key=lambda x: str(x.get("updated_at") or ""), reverse=True)
    return items


@router.get("/{scenario_id}")
async def get_api_scenario(
    scenario_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    with _LOCK:
        items = _load_all()
        for item in items:
            if item.get("id") == scenario_id:
                target_project_id = item.get("project_id")
                if target_project_id:
                    await assert_project_access(db, current_user, target_project_id, ProjectRole.viewer)
                return item
    raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="场景不存在")


@router.post("", status_code=status.HTTP_201_CREATED)
async def create_api_scenario(
    body: ApiScenarioSaveIn,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    await assert_project_access(db, current_user, body.project_id, ProjectRole.editor)
    bound_steps = await _bind_source_cases(db, body.project_id, body.steps)
    now = datetime.now(timezone.utc).isoformat()
    with _LOCK:
        items = _load_all()
        next_id = max((int(item.get("id", 0)) for item in items), default=0) + 1
        record = {
            "id": next_id,
            "scenario_code": f"SCN-{next_id:04d}",
            "project_id": body.project_id,
            "module_id": body.module_id,
            "name": body.name.strip(),
            "description": body.description.strip(),
            "env_id": body.env_id,
            "steps": bound_steps,
            "step_count": len(bound_steps),
            "last_run_status": None,
            "last_run_duration_ms": None,
            "last_run_at": None,
            "created_at": now,
            "updated_at": now,
        }
        items.append(record)
        _save_all(items)
        return record


@router.put("/{scenario_id}")
async def update_api_scenario(
    scenario_id: int,
    body: ApiScenarioSaveIn,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    await assert_project_access(db, current_user, body.project_id, ProjectRole.editor)
    bound_steps = await _bind_source_cases(db, body.project_id, body.steps, preserve_existing=True)
    now = datetime.now(timezone.utc).isoformat()
    with _LOCK:
        items = _load_all()
        for idx, item in enumerate(items):
            if item.get("id") == scenario_id:
                old_project_id = item.get("project_id")
                if old_project_id and old_project_id != body.project_id:
                    await assert_project_access(db, current_user, old_project_id, ProjectRole.editor)
                updated = {
                    **item,
                    "project_id": body.project_id,
                    "module_id": body.module_id,
                    "name": body.name.strip(),
                    "description": body.description.strip(),
                    "env_id": body.env_id,
                    "steps": bound_steps,
                    "step_count": len(bound_steps),
                    "updated_at": now,
                }
                items[idx] = updated
                _save_all(items)
                return updated
    raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="场景不存在")


@router.post("/{scenario_id}/record-run")
async def record_api_scenario_run(
    scenario_id: int,
    body: ApiScenarioRunRecordIn,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    now = datetime.now(timezone.utc).isoformat()
    with _LOCK:
        items = _load_all()
        for idx, item in enumerate(items):
            if item.get("id") == scenario_id:
                target_project_id = item.get("project_id")
                if target_project_id:
                    await assert_project_access(db, current_user, target_project_id, ProjectRole.viewer)
                updated = {
                    **item,
                    "last_run_status": body.status,
                    "last_run_duration_ms": body.duration_ms,
                    "last_run_at": now,
                    "updated_at": now,
                }
                items[idx] = updated
                _save_all(items)
                return updated
    raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="场景不存在")


@router.delete("/{scenario_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_api_scenario(
    scenario_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    with _LOCK:
        items = _load_all()
        target_item = next((item for item in items if item.get("id") == scenario_id), None)
        if not target_item:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="场景不存在")

        target_project_id = target_item.get("project_id")
        if target_project_id:
            await assert_project_access(db, current_user, target_project_id, ProjectRole.editor)

        filtered = [item for item in items if item.get("id") != scenario_id]
        _save_all(filtered)
    return None


class WorkflowDagValidateIn(BaseModel):
    nodes: list[dict[str, Any]] = Field(default_factory=list)


class WorkflowDagExecuteIn(BaseModel):
    nodes: list[dict[str, Any]] = Field(default_factory=list)
    initial_context: dict[str, Any] = Field(default_factory=dict)
    failure_strategy: str = "stop"


@router.post("/validate-dag")
async def validate_workflow_dag_endpoint(
    body: WorkflowDagValidateIn,
    _user: User = Depends(get_current_user),
):
    """校验混合工作流流程图的依赖合法性与拓扑结构，检测环路依赖并输出执行顺序。"""
    try:
        sorted_nodes = validate_and_toposort_workflow(body.nodes)
        return {
            "valid": True,
            "total_nodes": len(sorted_nodes),
            "execution_order": [str(n.get("id")) for n in sorted_nodes],
            "sorted_nodes": sorted_nodes,
        }
    except WorkflowDagError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/execute-dag")
async def execute_workflow_dag_endpoint(
    body: WorkflowDagExecuteIn,
    _user: User = Depends(get_current_user),
):
    """执行多协议混合工作流有向无环图（DAG），支持 HTTP -> SQL -> Redis -> 移动端节点调度。"""
    try:
        return await execute_workflow_dag(
            {"nodes": body.nodes},
            initial_context=body.initial_context,
            failure_strategy=body.failure_strategy,
        )
    except WorkflowDagError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


class WorkflowDataflowValidateIn(BaseModel):
    nodes: list[dict[str, Any]] = Field(default_factory=list)
    initial_context: dict[str, Any] = Field(default_factory=dict)
    strict: bool = False


@router.post("/validate-dataflow")
async def validate_workflow_dataflow_endpoint(
    body: WorkflowDataflowValidateIn,
    _user: User = Depends(get_current_user),
):
    """静态校验工作流节点间上下文变量双向数据流拓扑，检测未声明变量与逆向引用。"""
    try:
        return validate_workflow_dataflow_topology(
            body.nodes,
            initial_context=body.initial_context,
            strict=body.strict,
        )
    except (WorkflowDataflowError, WorkflowDagError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


class WorkflowDebugStartIn(BaseModel):
    nodes: list[dict[str, Any]] = Field(default_factory=list)
    breakpoints: list[str] = Field(default_factory=list)
    initial_context: dict[str, Any] = Field(default_factory=dict)
    watchers: list[str] = Field(default_factory=list)


@router.post("/debug/start")
async def start_workflow_debug_endpoint(
    body: WorkflowDebugStartIn,
    _user: User = Depends(get_current_user),
):
    """启动工作流画布断点调试会话，在入口处暂停并初始化变量观察器。"""
    try:
        return create_debug_session(
            {"nodes": body.nodes},
            breakpoints=body.breakpoints,
            initial_context=body.initial_context,
            watchers=body.watchers,
        )
    except (WorkflowDebuggerError, WorkflowDagError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/debug/{session_id}/step")
async def step_workflow_debug_endpoint(
    session_id: str,
    _user: User = Depends(get_current_user),
):
    """单步步过（Step Over）执行当前节点，并在下一个节点前暂停，返回最新的变量差分快照。"""
    try:
        return await step_debug_session(session_id)
    except WorkflowDebuggerError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post("/debug/{session_id}/resume")
async def resume_workflow_debug_endpoint(
    session_id: str,
    _user: User = Depends(get_current_user),
):
    """继续执行（Resume）调试会话，直到命中下一个断点或执行完毕。"""
    try:
        return await resume_debug_session(session_id)
    except WorkflowDebuggerError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.get("/debug/{session_id}")
async def get_workflow_debug_endpoint(
    session_id: str,
    _user: User = Depends(get_current_user),
):
    """获取指定调试会话当前运行状态、上下文变量快照与变量观察器数据。"""
    try:
        return get_debug_session(session_id)
    except WorkflowDebuggerError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.delete("/debug/{session_id}", status_code=status.HTTP_204_NO_CONTENT)
async def stop_workflow_debug_endpoint(
    session_id: str,
    _user: User = Depends(get_current_user),
):
    """终止并释放工作流调试会话。"""
    stopped = stop_debug_session(session_id)
    if not stopped:
        raise HTTPException(status_code=404, detail="调试会话不存在或已释放")
    return None
