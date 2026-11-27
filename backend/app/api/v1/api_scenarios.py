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
from app.models.user_project import ProjectRole, UserProject
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
from app.services.api_debug_session import (
    ApiDebugSessionError,
    DebugExecuteMode,
    PrecheckMode,
    create_api_debug_session,
    delete_api_debug_session,
    execute_api_debug_session,
    get_api_debug_session,
    precheck_api_scenario_steps,
    recheck_api_debug_assertions,
)
from app.services.api_scenario_sync import (
    SyncChoice,
    apply_step_sync,
    build_case_sync_metadata,
    compute_overridden_fields,
    compute_step_sync_diff,
    extract_case_request_snapshot,
)
from app.services.variable_loader import load_environment_variables_map, load_global_variables_map
from app.models.environment import Environment

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
    version: int | None = Field(default=None, ge=1)
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
            bound.pop("sourceSnapshot", None)
            bound.pop("overriddenFields", None)
        elif not preserve_existing or not (isinstance(fingerprint, str) and re.fullmatch(r"[0-9a-f]{64}", fingerprint)):
            snap = extract_case_request_snapshot(source)
            bound["sourceCaseFingerprint"] = case_request_fingerprint(source)
            bound["sourceSnapshot"] = snap
            bound["overriddenFields"] = compute_overridden_fields(bound, snap)
        elif isinstance(step.get("sourceSnapshot"), dict):
            bound["overriddenFields"] = compute_overridden_fields(bound, step.get("sourceSnapshot"))
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
    # Batch-compute stale_step_count for all referenced source cases (no N+1)
    source_ids = {
        step.get("sourceCaseId")
        for s in items
        for step in (s.get("steps") or [])
        if isinstance(step, dict)
        and isinstance(step.get("sourceCaseId"), int)
        and not isinstance(step.get("sourceCaseId"), bool)
    }
    latest_by_id: dict[int, tuple[dict[str, Any], str]] = {}
    if source_ids:
        res = await db.execute(select(TestCase).where(TestCase.id.in_(source_ids)))
        for c in res.scalars().all():
            latest_by_id[c.id] = build_case_sync_metadata(c)
    enriched: list[dict[str, Any]] = []
    for s in items:
        stale_count = 0
        conflict_count = 0
        for step in s.get("steps") or []:
            if not isinstance(step, dict):
                continue
            sid = step.get("sourceCaseId")
            if isinstance(sid, int) and sid in latest_by_id:
                snap, fp = latest_by_id[sid]
                diff = compute_step_sync_diff(step, snap, fp)
                if diff["sync_status"] == "stale_auto_syncable":
                    stale_count += 1
                elif diff["sync_status"] == "conflict":
                    stale_count += 1
                    conflict_count += 1
        enriched.append(
            {
                **s,
                "version": int(s.get("version") or 1),
                "stale_step_count": stale_count,
                "conflict_step_count": conflict_count,
            }
        )
    return enriched


@router.get("/{scenario_id}")
async def get_api_scenario(
    scenario_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    with _LOCK:
        items = _load_all()
        found = next((dict(item) for item in items if item.get("id") == scenario_id), None)
    if found is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="场景不存在")
    target_project_id = found.get("project_id")
    if target_project_id:
        await assert_project_access(db, current_user, target_project_id, ProjectRole.viewer)
    return found


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
            "version": 1,
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
    with _LOCK:
        existing_items = _load_all()
        old_item = next((dict(item) for item in existing_items if item.get("id") == scenario_id), None)
    if old_item is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="场景不存在")

    old_project_id = old_item.get("project_id")
    if old_project_id and old_project_id != body.project_id:
        await assert_project_access(db, current_user, old_project_id, ProjectRole.editor)

    bound_steps = await _bind_source_cases(db, body.project_id, body.steps, preserve_existing=True)
    now = datetime.now(timezone.utc).isoformat()
    with _LOCK:
        items = _load_all()
        for idx, item in enumerate(items):
            if item.get("id") == scenario_id:
                current_version = int(item.get("version") or 1)
                if body.version is not None and body.version != current_version:
                    raise HTTPException(
                        status_code=status.HTTP_409_CONFLICT,
                        detail=f"场景已被他人更新（当前版本 v{current_version}，提交版本 v{body.version}），请刷新后重试",
                    )
                updated = {
                    **item,
                    "project_id": body.project_id,
                    "module_id": body.module_id,
                    "name": body.name.strip(),
                    "description": body.description.strip(),
                    "env_id": body.env_id,
                    "version": current_version + 1,
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
    with _LOCK:
        existing_items = _load_all()
        target_item = next((dict(item) for item in existing_items if item.get("id") == scenario_id), None)
    if target_item is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="场景不存在")

    target_project_id = target_item.get("project_id")
    if target_project_id:
        await assert_project_access(db, current_user, target_project_id, ProjectRole.editor)

    now = datetime.now(timezone.utc).isoformat()
    with _LOCK:
        items = _load_all()
        for idx, item in enumerate(items):
            if item.get("id") == scenario_id:
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
        existing_items = _load_all()
        target_item = next((dict(item) for item in existing_items if item.get("id") == scenario_id), None)
    if not target_item:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="场景不存在")

    target_project_id = target_item.get("project_id")
    if target_project_id:
        await assert_project_access(db, current_user, target_project_id, ProjectRole.editor)

    with _LOCK:
        items = _load_all()
        if not any(item.get("id") == scenario_id for item in items):
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="场景不存在")
        filtered = [item for item in items if item.get("id") != scenario_id]
        _save_all(filtered)
    return None


class WorkflowDagValidateIn(BaseModel):
    nodes: list[dict[str, Any]] = Field(default_factory=list)


class WorkflowDagExecuteIn(BaseModel):
    nodes: list[dict[str, Any]] = Field(default_factory=list)
    initial_context: dict[str, Any] = Field(default_factory=dict)
    failure_strategy: str = "stop"


async def _require_workflow_editor(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> User:
    """工作流 DAG 执行与调试至少要求是系统管理员或任一项目的 editor（拦截全站只读 viewer）。"""
    if getattr(current_user, "role", None) == UserRole.admin:
        return current_user
    membership = (
        (
            await db.execute(
                select(UserProject).where(
                    UserProject.user_id == current_user.id,
                    UserProject.role.in_([ProjectRole.owner, ProjectRole.editor]),
                )
            )
        )
        .scalars()
        .first()
    )
    if membership is None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="需要项目编辑者（editor）及以上权限才能执行或调试工作流",
        )
    return current_user


def _workflow_actor(user: User) -> tuple[int | None, bool]:
    return getattr(user, "id", None), getattr(user, "role", None) == UserRole.admin


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
    _user: User = Depends(_require_workflow_editor),
):
    """执行多协议混合工作流有向无环图（DAG），支持 HTTP -> SQL -> Redis -> 移动端节点调度。"""
    try:
        return await execute_workflow_dag(
            {"nodes": body.nodes},
            initial_context=body.initial_context,
            failure_strategy=body.failure_strategy,
        )
    except (WorkflowDagError, ValueError) as exc:
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
    _user: User = Depends(_require_workflow_editor),
):
    """启动工作流画布断点调试会话，在入口处暂停并初始化变量观察器。"""
    owner_id, _ = _workflow_actor(_user)
    try:
        kwargs: dict[str, Any] = {
            "breakpoints": body.breakpoints,
            "initial_context": body.initial_context,
            "watchers": body.watchers,
        }
        if owner_id is not None:
            kwargs["owner_id"] = owner_id
        return create_debug_session({"nodes": body.nodes}, **kwargs)
    except (WorkflowDebuggerError, WorkflowDagError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/debug/{session_id}/step")
async def step_workflow_debug_endpoint(
    session_id: str,
    _user: User = Depends(_require_workflow_editor),
):
    """单步步过（Step Over）执行当前节点，并在下一个节点前暂停，返回最新的变量差分快照。"""
    actor_id, is_admin = _workflow_actor(_user)
    try:
        kwargs: dict[str, Any] = {}
        if actor_id is not None or is_admin:
            kwargs = {"actor_id": actor_id, "is_admin": is_admin}
        return await step_debug_session(session_id, **kwargs)
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    except WorkflowDebuggerError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post("/debug/{session_id}/resume")
async def resume_workflow_debug_endpoint(
    session_id: str,
    _user: User = Depends(_require_workflow_editor),
):
    """继续执行（Resume）调试会话，直到命中下一个断点或执行完毕。"""
    actor_id, is_admin = _workflow_actor(_user)
    try:
        kwargs: dict[str, Any] = {}
        if actor_id is not None or is_admin:
            kwargs = {"actor_id": actor_id, "is_admin": is_admin}
        return await resume_debug_session(session_id, **kwargs)
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    except WorkflowDebuggerError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.get("/debug/{session_id}")
async def get_workflow_debug_endpoint(
    session_id: str,
    _user: User = Depends(_require_workflow_editor),
):
    """获取指定调试会话当前运行状态、上下文变量快照与变量观察器数据。"""
    actor_id, is_admin = _workflow_actor(_user)
    try:
        kwargs: dict[str, Any] = {}
        if actor_id is not None or is_admin:
            kwargs = {"actor_id": actor_id, "is_admin": is_admin}
        return get_debug_session(session_id, **kwargs)
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    except WorkflowDebuggerError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.delete("/debug/{session_id}", status_code=status.HTTP_204_NO_CONTENT)
async def stop_workflow_debug_endpoint(
    session_id: str,
    _user: User = Depends(_require_workflow_editor),
):
    """终止并释放工作流调试会话。"""
    actor_id, is_admin = _workflow_actor(_user)
    try:
        kwargs: dict[str, Any] = {}
        if actor_id is not None or is_admin:
            kwargs = {"actor_id": actor_id, "is_admin": is_admin}
        stopped = stop_debug_session(session_id, **kwargs)
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    if not stopped:
        raise HTTPException(status_code=404, detail="调试会话不存在或已释放")
    return None


class ApiScenarioPrecheckIn(BaseModel):
    project_id: int
    env_id: int | None = None
    mode: PrecheckMode = "run"
    target_step_uid: str | None = None
    steps: list[dict[str, Any]] = Field(default_factory=list)
    extra_vars: dict[str, Any] = Field(default_factory=dict)


class ApiDebugSessionCreateIn(BaseModel):
    project_id: int
    editor_id: str = "default"
    env_id: int | None = None


class ApiDebugSessionExecuteIn(BaseModel):
    steps: list[dict[str, Any]] = Field(default_factory=list)
    target_step_uid: str | None = None
    mode: DebugExecuteMode = "single"
    extra_vars: dict[str, Any] = Field(default_factory=dict)


class ApiDebugSessionRecheckIn(BaseModel):
    steps: list[dict[str, Any]] = Field(default_factory=list)
    target_step_uid: str
    extra_vars: dict[str, Any] = Field(default_factory=dict)


async def _load_scenario_env_vars(
    db: AsyncSession,
    project_id: int,
    env_id: int | None,
    extra_vars: dict[str, Any] | None = None,
) -> dict[str, Any]:
    merged: dict[str, Any] = await load_global_variables_map(db, project_id)
    if env_id is not None:
        env = await db.get(Environment, env_id)
        if env is not None and env.project_id == project_id:
            if getattr(env, "base_url", None):
                merged.setdefault("base_url", env.base_url)
            env_vars = await load_environment_variables_map(db, env_id)
            merged.update(env_vars)
    if extra_vars:
        merged.update(extra_vars)
    return merged


@router.post("/precheck")
async def precheck_api_scenario_endpoint(
    body: ApiScenarioPrecheckIn,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """三层预检（save / debug / run），返回带步骤与面板定位的结构化问题清单。"""
    await assert_project_access(db, current_user, body.project_id, ProjectRole.viewer)
    env_vars = await _load_scenario_env_vars(db, body.project_id, body.env_id, body.extra_vars)
    issues = precheck_api_scenario_steps(
        body.steps,
        env_vars=env_vars,
        mode=body.mode,
        target_step_uid=body.target_step_uid,
    )
    return {"valid": len(issues) == 0, "mode": body.mode, "issues": issues}


@router.post("/debug-sessions", status_code=status.HTTP_201_CREATED)
async def create_api_debug_session_endpoint(
    body: ApiDebugSessionCreateIn,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """创建按用户/编辑器/环境隔离的接口调试会话。"""
    await assert_project_access(db, current_user, body.project_id, ProjectRole.editor)
    try:
        sess = create_api_debug_session(
            user_id=current_user.id,
            project_id=body.project_id,
            editor_id=body.editor_id,
            env_id=body.env_id,
        )
    except ApiDebugSessionError as exc:
        raise HTTPException(status_code=exc.status_code, detail=str(exc)) from exc
    return {
        "session_id": sess.session_id,
        "project_id": sess.project_id,
        "editor_id": sess.editor_id,
        "env_id": sess.env_id,
    }


@router.post("/debug-sessions/{session_id}/execute")
async def execute_api_debug_session_endpoint(
    session_id: str,
    body: ApiDebugSessionExecuteIn,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """在隔离调试会话中执行单步（single）、从头到此步（through）或收集模式（collect）。"""
    try:
        sess = get_api_debug_session(
            session_id,
            user_id=current_user.id,
            is_admin=current_user.role == UserRole.admin,
        )
        await assert_project_access(db, current_user, sess.project_id, ProjectRole.editor)
        env_vars = await _load_scenario_env_vars(db, sess.project_id, sess.env_id, body.extra_vars)
        return await execute_api_debug_session(
            sess,
            steps=body.steps,
            target_step_uid=body.target_step_uid,
            mode=body.mode,
            env_vars=env_vars,
            db=db,
        )
    except ApiDebugSessionError as exc:
        raise HTTPException(status_code=exc.status_code, detail=str(exc)) from exc


@router.post("/debug-sessions/{session_id}/recheck-assertions")
async def recheck_api_debug_assertions_endpoint(
    session_id: str,
    body: ApiDebugSessionRecheckIn,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """不发送 HTTP 请求，基于当前会话缓存的真实响应离线重算修改后的断言。"""
    try:
        sess = get_api_debug_session(
            session_id,
            user_id=current_user.id,
            is_admin=current_user.role == UserRole.admin,
        )
        await assert_project_access(db, current_user, sess.project_id, ProjectRole.editor)
        env_vars = await _load_scenario_env_vars(db, sess.project_id, sess.env_id, body.extra_vars)
        return await recheck_api_debug_assertions(
            sess,
            steps=body.steps,
            target_step_uid=body.target_step_uid,
            env_vars=env_vars,
            db=db,
        )
    except ApiDebugSessionError as exc:
        raise HTTPException(status_code=exc.status_code, detail=str(exc)) from exc


@router.delete("/debug-sessions/{session_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_api_debug_session_endpoint(
    session_id: str,
    current_user: User = Depends(get_current_user),
):
    """释放接口调试会话缓存。"""
    try:
        delete_api_debug_session(
            session_id,
            user_id=current_user.id,
            is_admin=current_user.role == UserRole.admin,
        )
    except ApiDebugSessionError as exc:
        raise HTTPException(status_code=exc.status_code, detail=str(exc)) from exc
    return None


class ScenarioSyncPreviewIn(BaseModel):
    scenario_id: int | None = None
    step_uid: str | None = None
    step: dict[str, Any] | None = None


class ScenarioSyncApplyItemIn(BaseModel):
    scenario_id: int
    scenario_version: int = Field(ge=1)
    step_uid: str
    choices: dict[str, SyncChoice] = Field(default_factory=dict)


class ScenarioSyncApplyIn(BaseModel):
    items: list[ScenarioSyncApplyItemIn] = Field(default_factory=list, max_length=200)


async def _load_source_api_case(
    db: AsyncSession,
    case_id: int,
    user: User,
    min_role: ProjectRole,
) -> tuple[TestCase, int]:
    result = await db.execute(
        select(TestCase, Module.project_id)
        .join(Module, TestCase.module_id == Module.id)
        .where(TestCase.id == case_id, TestCase.case_type == CaseType.api)
    )
    row = result.first()
    if row is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="源 API 用例不存在")
    case_obj, proj_id = row[0], int(row[1])
    await assert_project_access(db, user, proj_id, min_role)
    return case_obj, proj_id


@router.get("/source-cases/{case_id}/usages")
async def get_source_case_scenario_usages(
    case_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """查询某条公共 API 用例被哪些场景的哪些步骤引用，以及每步的同步状态与冲突字段。"""
    source_case, proj_id = await _load_source_api_case(db, case_id, current_user, ProjectRole.viewer)
    latest_snapshot, latest_fp = build_case_sync_metadata(source_case)

    with _LOCK:
        scenarios = [s for s in _load_all() if s.get("project_id") == proj_id]

    usages: list[dict[str, Any]] = []
    total_steps = 0
    stale_steps = 0
    conflict_steps = 0

    for sc in scenarios:
        matched_steps: list[dict[str, Any]] = []
        for idx, step in enumerate(sc.get("steps") or []):
            if not isinstance(step, dict) or step.get("sourceCaseId") != case_id:
                continue
            total_steps += 1
            diff = compute_step_sync_diff(step, latest_snapshot, latest_fp)
            if diff["sync_status"] == "stale_auto_syncable":
                stale_steps += 1
            elif diff["sync_status"] == "conflict":
                stale_steps += 1
                conflict_steps += 1
            matched_steps.append(
                {
                    "step_uid": str(step.get("uid") or f"step_{idx + 1}"),
                    "step_index": idx,
                    "step_name": str(step.get("name") or f"步骤 {idx + 1}"),
                    "sync_status": diff["sync_status"],
                    "auto_update_fields": [item["field"] for item in diff["auto_updates"]],
                    "conflict_fields": [item["field"] for item in diff["conflicts"]],
                    "overridden_fields": diff["overridden_fields"],
                }
            )
        if matched_steps:
            usages.append(
                {
                    "scenario_id": sc.get("id"),
                    "scenario_code": sc.get("scenario_code"),
                    "scenario_name": sc.get("name"),
                    "scenario_version": int(sc.get("version") or 1),
                    "steps": matched_steps,
                }
            )

    return {
        "case_id": case_id,
        "case_name": source_case.name,
        "latest_fingerprint": latest_fp,
        "total_scenarios": len(usages),
        "total_steps": total_steps,
        "stale_steps": stale_steps,
        "conflict_steps": conflict_steps,
        "scenarios": usages,
    }


@router.post("/source-cases/{case_id}/sync-preview")
async def preview_source_case_sync(
    case_id: int,
    body: ScenarioSyncPreviewIn,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """预览指定场景步骤与源用例最新模板之间的逐字段差异与冲突，不自动落库。"""
    source_case, proj_id = await _load_source_api_case(db, case_id, current_user, ProjectRole.viewer)
    latest_snapshot, latest_fp = build_case_sync_metadata(source_case)

    target_step = body.step
    if target_step is None:
        if body.scenario_id is None or not body.step_uid:
            raise HTTPException(status_code=422, detail="必须提供 step 或 (scenario_id + step_uid)")
        with _LOCK:
            sc = next(
                (
                    item
                    for item in _load_all()
                    if item.get("id") == body.scenario_id and item.get("project_id") == proj_id
                ),
                None,
            )
        if sc is None:
            raise HTTPException(status_code=404, detail="目标场景不存在")
        for idx, st in enumerate(sc.get("steps") or []):
            if isinstance(st, dict) and str(st.get("uid") or f"step_{idx + 1}") == body.step_uid:
                target_step = st
                break
        if target_step is None:
            raise HTTPException(status_code=404, detail="目标步骤不存在")

    diff = compute_step_sync_diff(target_step, latest_snapshot, latest_fp)
    return {
        "case_id": case_id,
        "latest_fingerprint": latest_fp,
        **diff,
    }


@router.post("/source-cases/{case_id}/sync-apply")
async def apply_source_case_sync_batch(
    case_id: int,
    body: ScenarioSyncApplyIn,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """冲突感知批量同步：无冲突步骤一键同步；冲突步骤必须提供逐字段选择；按乐观锁 version 保护。"""
    source_case, proj_id = await _load_source_api_case(db, case_id, current_user, ProjectRole.editor)
    latest_snapshot, latest_fp = build_case_sync_metadata(source_case)
    now = datetime.now(timezone.utc).isoformat()

    results: list[dict[str, Any]] = []
    applied = 0
    failed = 0

    with _LOCK:
        all_items = _load_all()
        changed_any = False
        initial_versions: dict[int, int] = {}
        mutated_scenarios: dict[int, int] = {}

        for req_item in body.items:
            sc_idx = next(
                (
                    i
                    for i, sc in enumerate(all_items)
                    if sc.get("id") == req_item.scenario_id and sc.get("project_id") == proj_id
                ),
                None,
            )
            if sc_idx is None:
                failed += 1
                results.append(
                    {
                        "scenario_id": req_item.scenario_id,
                        "step_uid": req_item.step_uid,
                        "ok": False,
                        "changed": False,
                        "reason": "场景不存在或不属于当前项目",
                    }
                )
                continue

            sc = all_items[sc_idx]
            if req_item.scenario_id not in initial_versions:
                initial_versions[req_item.scenario_id] = int(sc.get("version") or 1)
            base_ver = initial_versions[req_item.scenario_id]
            if base_ver != req_item.scenario_version:
                failed += 1
                results.append(
                    {
                        "scenario_id": req_item.scenario_id,
                        "step_uid": req_item.step_uid,
                        "ok": False,
                        "changed": False,
                        "version": base_ver,
                        "reason": f"场景版本已变更为 v{base_ver}，请刷新后重试",
                    }
                )
                continue

            steps_list = [dict(st) if isinstance(st, dict) else st for st in (sc.get("steps") or [])]
            target_idx = next(
                (
                    i
                    for i, st in enumerate(steps_list)
                    if isinstance(st, dict)
                    and st.get("sourceCaseId") == case_id
                    and str(st.get("uid") or f"step_{i + 1}") == req_item.step_uid
                ),
                None,
            )
            if target_idx is None:
                failed += 1
                results.append(
                    {
                        "scenario_id": req_item.scenario_id,
                        "step_uid": req_item.step_uid,
                        "ok": False,
                        "changed": False,
                        "reason": "步骤不存在或未引用该源用例",
                    }
                )
                continue

            updated_step, unresolved = apply_step_sync(
                steps_list[target_idx],
                latest_snapshot,
                latest_fp,
                req_item.choices,
            )
            if unresolved:
                failed += 1
                results.append(
                    {
                        "scenario_id": req_item.scenario_id,
                        "step_uid": req_item.step_uid,
                        "ok": False,
                        "changed": False,
                        "reason": "存在需要逐项确认的冲突字段",
                        "conflicts": unresolved,
                    }
                )
                continue

            steps_list[target_idx] = updated_step
            sc = dict(sc)
            sc["steps"] = steps_list
            all_items[sc_idx] = sc
            mutated_scenarios[req_item.scenario_id] = sc_idx
            changed_any = True
            applied += 1
            results.append(
                {
                    "scenario_id": req_item.scenario_id,
                    "step_uid": req_item.step_uid,
                    "ok": True,
                    "changed": True,
                    "version": base_ver + 1,
                }
            )

        for sc_id, sc_idx in mutated_scenarios.items():
            sc = dict(all_items[sc_idx])
            sc["version"] = initial_versions[sc_id] + 1
            sc["updated_at"] = now
            all_items[sc_idx] = sc

        if changed_any:
            _save_all(all_items)

    return {
        "case_id": case_id,
        "applied": applied,
        "failed": failed,
        "items": results,
    }
