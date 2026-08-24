"""Internal defect management and sanitized failed-run evidence links."""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any
from urllib.parse import urlsplit, urlunsplit

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.api.deps import assert_project_access, get_current_user
from app.core.database import get_db
from app.models.case import StepResult, TestCase, TestRun
from app.models.defect import Defect, DefectRunLink
from app.models.mobile_special import MobileIncident, MobileRunArtifact, MobileSpecialRun, MobileSpecialTask
from app.models.performance import PerformanceRun, PerformanceTest
from app.models.plan import PlanRun, TestPlan
from app.models.project import Module, Project
from app.models.suite import SuiteRun, TestSuite
from app.models.user import User, UserRole
from app.models.user_project import ProjectRole, UserProject
from app.schemas.defect import (
    DefectCreate,
    DefectCreateFromRun,
    DefectListOut,
    DefectMutationOut,
    DefectOut,
    DefectRunLinkCreate,
    DefectRunLinkOut,
    DefectUpdate,
)
from app.services.audit import write_audit_log
from app.services.project_scope import scope_to_visible_projects

router = APIRouter(tags=["缺陷管理"])

_RUN_TYPES = {"case", "suite", "plan", "android", "performance"}
_FAILED_RUN_STATUSES = {"failed", "error", "cancelled", "stopped"}
_ACTIVE_DUPLICATE_STATUSES = {"open", "in_progress", "reopened"}
_STATUS_TRANSITIONS: dict[str, set[str]] = {
    "open": {"in_progress", "resolved", "closed"},
    "in_progress": {"open", "resolved"},
    "resolved": {"reopened", "closed"},
    "reopened": {"in_progress", "resolved"},
    "closed": {"reopened"},
}
_SECRET_PATTERN = re.compile(
    r"(?i)(authorization|cookie|set-cookie|password|passwd|token|secret|api[_-]?key)\s*[:=]\s*(?:bearer\s+)?[^,;\n]+"
)
_SENSITIVE_KEY_PATTERN = re.compile(r"(?i)(authorization|cookie|set-cookie|password|passwd|token|secret|api[_-]?key)")


@dataclass(frozen=True)
class _RunContext:
    project_id: int
    case_id: int | None
    title: str
    status: str
    error_message: str | None
    trace_id: str | None
    evidence: dict[str, Any]


def _value(value: Any) -> str:
    return str(getattr(value, "value", value))


def _safe_text(value: Any, limit: int = 2_000) -> str | None:
    if value is None:
        return None
    text = str(value)
    text = _SECRET_PATTERN.sub(lambda match: f"{match.group(1)}=[REDACTED]", text)
    return text[:limit]


def _safe_asset_ref(value: Any) -> str | None:
    if not value:
        return None
    raw = str(value)
    try:
        parsed = urlsplit(raw)
        if parsed.scheme or parsed.netloc:
            return urlunsplit((parsed.scheme, parsed.netloc, parsed.path, "", ""))[:512]
    except ValueError:
        return None
    return raw.split("?", 1)[0].split("#", 1)[0][:512]


def _safe_json(value: Any, depth: int = 0) -> Any:
    """Copy small evidence summaries while redacting nested strings and limiting size."""
    if depth > 3:
        return "[TRUNCATED]"
    if isinstance(value, str):
        return _safe_text(value, 1_000)
    if isinstance(value, dict):
        safe_items = {}
        for key, item in list(value.items())[:100]:
            safe_key = str(key)[:128]
            safe_items[safe_key] = (
                "[REDACTED]" if _SENSITIVE_KEY_PATTERN.search(safe_key) else _safe_json(item, depth + 1)
            )
        return safe_items
    if isinstance(value, list):
        return [_safe_json(item, depth + 1) for item in value[:100]]
    if isinstance(value, (int, float, bool)) or value is None:
        return value
    return _safe_text(value, 256)


def _fingerprint(project_id: int, title: str, error_message: str | None) -> str:
    normalized = " ".join((error_message or "").lower().split())[:1_000]
    return hashlib.sha256(f"{project_id}|{title.lower().strip()}|{normalized}".encode("utf-8")).hexdigest()


def _serialize_link(link: DefectRunLink) -> DefectRunLinkOut:
    return DefectRunLinkOut(
        id=link.id,
        run_type=link.run_type,
        run_id=link.run_id,
        case_id=link.case_id,
        evidence=link.evidence or {},
        linked_by=link.linked_by,
        created_at=link.created_at,
    )


def _serialize_defect(defect: Defect) -> DefectOut:
    return DefectOut(
        id=defect.id,
        project_id=defect.project_id,
        case_id=defect.case_id,
        title=defect.title,
        description=defect.description,
        status=defect.status,
        priority=defect.priority,
        severity=defect.severity,
        fingerprint=defect.fingerprint,
        resolution=defect.resolution,
        labels=defect.labels or [],
        occurrence_count=defect.occurrence_count,
        last_seen_at=defect.last_seen_at,
        creator_id=defect.creator_id,
        assignee_id=defect.assignee_id,
        created_at=defect.created_at,
        updated_at=defect.updated_at,
        run_links=[_serialize_link(link) for link in (defect.run_links or [])],
    )


async def _get_defect(db: AsyncSession, defect_id: int, user: User, min_role: ProjectRole) -> Defect:
    result = await db.execute(select(Defect).where(Defect.id == defect_id).options(selectinload(Defect.run_links)))
    defect = result.scalar_one_or_none()
    if defect is None:
        raise HTTPException(status_code=404, detail="内部缺陷不存在")
    await assert_project_access(db, user, defect.project_id, min_role)
    return defect


async def _ensure_assignee(db: AsyncSession, project_id: int, assignee_id: int | None, user: User) -> None:
    if assignee_id is None:
        return
    assignee = await db.get(User, assignee_id)
    if assignee is None or not assignee.is_active:
        raise HTTPException(status_code=400, detail="指派用户不存在或已禁用")
    if getattr(user, "role", None) == UserRole.admin:
        return
    membership = await db.execute(
        select(UserProject.id).where(UserProject.user_id == assignee_id, UserProject.project_id == project_id)
    )
    if membership.scalar_one_or_none() is None:
        raise HTTPException(status_code=400, detail="指派用户不是该项目成员")


async def _ensure_case_project(db: AsyncSession, project_id: int, case_id: int | None) -> None:
    if case_id is None:
        return
    case = await db.get(TestCase, case_id)
    module = await db.get(Module, case.module_id) if case else None
    if case is None or module is None:
        raise HTTPException(status_code=404, detail="关联用例不存在")
    if module.project_id != project_id:
        raise HTTPException(status_code=400, detail="关联用例不属于该项目")


def _case_evidence(run: TestRun, case: TestCase, steps: list[StepResult]) -> dict[str, Any]:
    step_items = []
    screenshot_refs = []
    for step in steps[:50]:
        screenshot = _safe_asset_ref(step.screenshot_url)
        if screenshot:
            screenshot_refs.append(screenshot)
        step_items.append(
            {
                "step_index": step.step_index,
                "name": _safe_text(step.name, 256),
                "status": _value(step.status),
                "error_message": _safe_text(step.error_message),
                "screenshot_ref": screenshot,
            }
        )
    return {
        "status": _value(run.status),
        "case_id": case.id,
        "case_name": _safe_text(case.name, 256),
        "environment": _safe_text(run.environment, 128),
        "trace_id": _safe_text(run.trace_id, 128),
        "error_message": _safe_text(run.error_message),
        "screenshot_refs": screenshot_refs[:50],
        "steps": step_items,
    }


async def _resolve_run_context(db: AsyncSession, run_type: str, run_id: int) -> _RunContext:
    if run_type not in _RUN_TYPES:
        raise HTTPException(status_code=422, detail="不支持的执行记录类型")

    if run_type == "case":
        run = await db.get(TestRun, run_id)
        case = await db.get(TestCase, run.case_id) if run else None
        module = await db.get(Module, case.module_id) if case else None
        if run is None or case is None or module is None:
            raise HTTPException(status_code=404, detail="用例执行记录不存在")
        result = await db.execute(select(StepResult).where(StepResult.run_id == run_id).order_by(StepResult.step_index))
        return _RunContext(
            project_id=module.project_id,
            case_id=case.id,
            title=f"{case.name} 执行失败",
            status=_value(run.status),
            error_message=_safe_text(run.error_message),
            trace_id=_safe_text(run.trace_id, 128),
            evidence=_case_evidence(run, case, list(result.scalars().all())),
        )

    if run_type == "suite":
        run = await db.get(SuiteRun, run_id)
        suite = await db.get(TestSuite, run.suite_id) if run else None
        if run is None or suite is None:
            raise HTTPException(status_code=404, detail="套件执行记录不存在")
        return _RunContext(
            project_id=suite.project_id,
            case_id=None,
            title=f"{suite.name} 套件执行失败",
            status=_value(run.status),
            error_message=_safe_text(run.error_message),
            trace_id=_safe_text(run.trace_id, 128),
            evidence={
                "status": _value(run.status),
                "suite_id": suite.id,
                "suite_name": _safe_text(suite.name, 256),
                "trace_id": _safe_text(run.trace_id, 128),
                "error_message": _safe_text(run.error_message),
                "case_run_ids": _safe_json(run.case_run_ids or []),
            },
        )

    if run_type == "plan":
        run = await db.get(PlanRun, run_id)
        plan = await db.get(TestPlan, run.plan_id) if run else None
        if run is None or plan is None:
            raise HTTPException(status_code=404, detail="计划执行记录不存在")
        return _RunContext(
            project_id=plan.project_id,
            case_id=None,
            title=f"{plan.name} 计划执行失败",
            status=_value(run.status),
            error_message=_safe_text(run.error_message),
            trace_id=_safe_text(run.trace_id, 128),
            evidence={
                "status": _value(run.status),
                "plan_id": plan.id,
                "plan_name": _safe_text(plan.name, 256),
                "trace_id": _safe_text(run.trace_id, 128),
                "error_message": _safe_text(run.error_message),
                "suite_run_ids": _safe_json(run.suite_run_ids or []),
            },
        )

    if run_type == "android":
        run = await db.get(MobileSpecialRun, run_id)
        task = await db.get(MobileSpecialTask, run.task_id) if run else None
        if run is None or task is None:
            raise HTTPException(status_code=404, detail="Android 专项执行记录不存在")
        artifact_result = await db.execute(select(MobileRunArtifact).where(MobileRunArtifact.run_id == run_id))
        incident_result = await db.execute(select(MobileIncident).where(MobileIncident.run_id == run_id))
        source_case_id = task.source_id if _value(task.source_type) == "case" else None
        return _RunContext(
            project_id=task.project_id,
            case_id=source_case_id,
            title=f"{task.name} Android 执行异常",
            status=_value(run.status),
            error_message=_safe_text((run.summary_json or {}).get("error")),
            trace_id=_safe_text((run.summary_json or {}).get("trace_id"), 128),
            evidence={
                "status": _value(run.status),
                "task_id": task.id,
                "task_name": _safe_text(task.name, 256),
                "device_serial": _safe_text(run.device_serial, 128),
                "app_package": _safe_text(run.app_package, 256),
                "trace_id": _safe_text((run.summary_json or {}).get("trace_id"), 128),
                "artifact_refs": [
                    {
                        "artifact_type": _value(item.artifact_type),
                        "file_name": _safe_text(item.file_name, 256),
                        "file_ref": _safe_asset_ref(item.file_path),
                    }
                    for item in artifact_result.scalars().all()[:100]
                ],
                "incidents": [
                    {
                        "incident_type": _value(item.incident_type),
                        "title": _safe_text(item.title, 512),
                        "detail": _safe_text(item.detail),
                        "event_time": item.event_time.isoformat() if item.event_time else None,
                    }
                    for item in incident_result.scalars().all()[:100]
                ],
            },
        )

    run = await db.get(PerformanceRun, run_id)
    test = await db.get(PerformanceTest, run.performance_test_id) if run else None
    if run is None or test is None:
        raise HTTPException(status_code=404, detail="性能执行记录不存在")
    return _RunContext(
        project_id=run.project_id,
        case_id=None,
        title=f"{test.name} 性能执行异常",
        status=_value(run.status),
        error_message=_safe_text(run.error_message),
        trace_id=None,
        evidence={
            "status": _value(run.status),
            "performance_test_id": test.id,
            "performance_test_name": _safe_text(test.name, 256),
            "error_message": _safe_text(run.error_message),
            "raw_result_ref": _safe_asset_ref(run.raw_result_object_name),
        },
    )


async def _find_duplicate(db: AsyncSession, project_id: int, fingerprint: str) -> Defect | None:
    result = await db.execute(
        select(Defect)
        .where(
            Defect.project_id == project_id,
            Defect.fingerprint == fingerprint,
            Defect.status.in_(_ACTIVE_DUPLICATE_STATUSES),
        )
        .options(selectinload(Defect.run_links))
        .order_by(Defect.updated_at.desc())
        .limit(1)
    )
    return result.scalar_one_or_none()


async def _attach_link(
    db: AsyncSession,
    defect: Defect,
    run_type: str,
    run_id: int,
    linked_by: int,
    case_id: int | None = None,
) -> DefectRunLink:
    context = await _resolve_run_context(db, run_type, run_id)
    if context.project_id != defect.project_id:
        raise HTTPException(status_code=400, detail="执行记录不属于该缺陷所在项目")
    if case_id is not None:
        await _ensure_case_project(db, defect.project_id, case_id)
    effective_case_id = case_id if case_id is not None else context.case_id
    if effective_case_id is not None:
        await _ensure_case_project(db, defect.project_id, effective_case_id)
    result = await db.execute(
        select(DefectRunLink).where(
            DefectRunLink.defect_id == defect.id,
            DefectRunLink.run_type == run_type,
            DefectRunLink.run_id == run_id,
        )
    )
    link = result.scalar_one_or_none()
    if link is None:
        link = DefectRunLink(
            defect_id=defect.id,
            run_type=run_type,
            run_id=run_id,
            case_id=effective_case_id,
            evidence=context.evidence,
            linked_by=linked_by,
        )
        db.add(link)
    else:
        link.case_id = effective_case_id
        link.evidence = context.evidence
        link.linked_by = linked_by
    if defect.case_id is None and effective_case_id is not None:
        defect.case_id = effective_case_id
    defect.last_seen_at = datetime.now(timezone.utc)
    return link


async def _load_defect_after_write(db: AsyncSession, defect_id: int) -> Defect:
    result = await db.execute(select(Defect).where(Defect.id == defect_id).options(selectinload(Defect.run_links)))
    defect = result.scalar_one()
    return defect


@router.get("/defects", response_model=DefectListOut)
async def list_defects(
    project_id: int | None = Query(default=None, ge=1),
    case_id: int | None = Query(default=None, ge=1),
    run_type: str | None = Query(default=None),
    run_id: int | None = Query(default=None, ge=1),
    status_filter: str | None = Query(default=None, alias="status"),
    priority: str | None = Query(default=None),
    severity: str | None = Query(default=None),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    if project_id is not None:
        await assert_project_access(db, user, project_id, ProjectRole.viewer)
    query = scope_to_visible_projects(select(Defect), Defect.project_id, user, project_id)
    if (run_type is None) != (run_id is None):
        raise HTTPException(status_code=422, detail="run_type 和 run_id 必须同时提供")
    if run_type is not None and run_type not in _RUN_TYPES:
        raise HTTPException(status_code=422, detail="不支持的执行记录类型")
    if run_type is not None and run_id is not None:
        query = query.where(
            Defect.id.in_(
                select(DefectRunLink.defect_id).where(
                    DefectRunLink.run_type == run_type,
                    DefectRunLink.run_id == run_id,
                )
            )
        )
    if case_id is not None:
        query = query.where(
            or_(
                Defect.case_id == case_id,
                Defect.id.in_(select(DefectRunLink.defect_id).where(DefectRunLink.case_id == case_id)),
            )
        )
    if status_filter:
        query = query.where(Defect.status == status_filter)
    if priority:
        query = query.where(Defect.priority == priority)
    if severity:
        query = query.where(Defect.severity == severity)
    total = int((await db.execute(select(func.count()).select_from(query.subquery()))).scalar_one() or 0)
    result = await db.execute(
        query.options(selectinload(Defect.run_links))
        .order_by(Defect.updated_at.desc(), Defect.id.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    return DefectListOut(
        items=[_serialize_defect(item) for item in result.scalars().all()],
        total=total,
        page=page,
        page_size=page_size,
    )


@router.post("/defects", response_model=DefectMutationOut)
async def create_defect(
    body: DefectCreate,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    await assert_project_access(db, user, body.project_id, ProjectRole.editor)
    if await db.get(Project, body.project_id) is None:
        raise HTTPException(status_code=404, detail="项目不存在")
    await _ensure_assignee(db, body.project_id, body.assignee_id, user)
    await _ensure_case_project(db, body.project_id, body.case_id)

    contexts: list[tuple[DefectRunLinkCreate, _RunContext]] = []
    for link in body.run_links:
        context = await _resolve_run_context(db, link.run_type, link.run_id)
        if context.project_id != body.project_id:
            raise HTTPException(status_code=400, detail="执行记录不属于该项目")
        if link.case_id is not None:
            await _ensure_case_project(db, body.project_id, link.case_id)
        contexts.append((link, context))

    first_error = next((context.error_message for _, context in contexts if context.error_message), body.description)
    fingerprint = body.fingerprint or _fingerprint(body.project_id, body.title, first_error)
    duplicate = await _find_duplicate(db, body.project_id, fingerprint)
    if duplicate:
        duplicate.occurrence_count = (duplicate.occurrence_count or 0) + 1
        duplicate.last_seen_at = datetime.now(timezone.utc)
        for link, _ in contexts:
            await _attach_link(db, duplicate, link.run_type, link.run_id, user.id, link.case_id)
        await write_audit_log(
            db,
            action="defect_duplicate_detected",
            resource_type="defect",
            resource_id=duplicate.id,
            user_id=user.id,
            username=user.username,
            project_id=duplicate.project_id,
            detail=f"创建缺陷命中重复记录: {duplicate.id}",
        )
        await db.commit()
        return DefectMutationOut(
            defect=_serialize_defect(await _load_defect_after_write(db, duplicate.id)),
            created=False,
            duplicate_of=duplicate.id,
        )

    defect = Defect(
        project_id=body.project_id,
        case_id=body.case_id or next((context.case_id for _, context in contexts if context.case_id), None),
        title=body.title,
        description=_safe_text(body.description, 20_000),
        status=body.status,
        priority=body.priority,
        severity=body.severity,
        fingerprint=fingerprint,
        labels=[label.strip()[:64] for label in body.labels if label.strip()][:20],
        creator_id=user.id,
        assignee_id=body.assignee_id,
        last_seen_at=datetime.now(timezone.utc) if contexts else None,
    )
    db.add(defect)
    await db.flush()
    for link, _ in contexts:
        await _attach_link(db, defect, link.run_type, link.run_id, user.id, link.case_id)
    await write_audit_log(
        db,
        action="defect_create",
        resource_type="defect",
        resource_id=defect.id,
        user_id=user.id,
        username=user.username,
        project_id=defect.project_id,
        detail=f"创建内部缺陷: {defect.title}",
    )
    await db.commit()
    return DefectMutationOut(defect=_serialize_defect(await _load_defect_after_write(db, defect.id)), created=True)


@router.post("/defects/from-run/{run_type}/{run_id}", response_model=DefectMutationOut)
async def create_defect_from_run(
    run_type: str,
    run_id: int,
    body: DefectCreateFromRun,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    context = await _resolve_run_context(db, run_type, run_id)
    if context.status not in _FAILED_RUN_STATUSES:
        raise HTTPException(status_code=409, detail="只能从失败或异常执行记录创建内部缺陷")
    await assert_project_access(db, user, context.project_id, ProjectRole.editor)
    await _ensure_assignee(db, context.project_id, body.assignee_id, user)
    title = (body.title or context.title).strip()
    if not title:
        raise HTTPException(status_code=422, detail="缺陷标题不能为空")
    fingerprint = _fingerprint(context.project_id, title, context.error_message)
    duplicate = await _find_duplicate(db, context.project_id, fingerprint)
    if duplicate:
        await _attach_link(db, duplicate, run_type, run_id, user.id, context.case_id)
        duplicate.occurrence_count = (duplicate.occurrence_count or 0) + 1
        duplicate.last_seen_at = datetime.now(timezone.utc)
        await write_audit_log(
            db,
            action="defect_duplicate_detected",
            resource_type="defect",
            resource_id=duplicate.id,
            user_id=user.id,
            username=user.username,
            project_id=duplicate.project_id,
            detail=f"失败运行 {run_type}:{run_id} 命中重复缺陷: {duplicate.id}",
        )
        await db.commit()
        return DefectMutationOut(
            defect=_serialize_defect(await _load_defect_after_write(db, duplicate.id)),
            created=False,
            duplicate_of=duplicate.id,
        )

    defect = Defect(
        project_id=context.project_id,
        case_id=context.case_id,
        title=title,
        description=_safe_text(body.description or context.error_message, 20_000),
        status="open",
        priority=body.priority,
        severity=body.severity,
        fingerprint=fingerprint,
        creator_id=user.id,
        assignee_id=body.assignee_id,
        last_seen_at=datetime.now(timezone.utc),
    )
    db.add(defect)
    await db.flush()
    await _attach_link(db, defect, run_type, run_id, user.id, context.case_id)
    await write_audit_log(
        db,
        action="defect_create_from_run",
        resource_type="defect",
        resource_id=defect.id,
        user_id=user.id,
        username=user.username,
        project_id=defect.project_id,
        detail=f"从失败运行创建内部缺陷: {run_type}:{run_id}",
    )
    await db.commit()
    return DefectMutationOut(defect=_serialize_defect(await _load_defect_after_write(db, defect.id)), created=True)


@router.get("/defects/{defect_id}", response_model=DefectOut)
async def get_defect(
    defect_id: int,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    return _serialize_defect(await _get_defect(db, defect_id, user, ProjectRole.viewer))


@router.patch("/defects/{defect_id}", response_model=DefectOut)
async def update_defect(
    defect_id: int,
    body: DefectUpdate,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    defect = await _get_defect(db, defect_id, user, ProjectRole.editor)
    fields = body.model_dump(exclude_unset=True)
    if "status" in fields and fields["status"] != defect.status:
        allowed = _STATUS_TRANSITIONS.get(defect.status, set())
        if fields["status"] not in allowed:
            raise HTTPException(status_code=409, detail=f"不允许从 {defect.status} 流转到 {fields['status']}")
    if "assignee_id" in fields:
        await _ensure_assignee(db, defect.project_id, fields["assignee_id"], user)
    if "title" in fields:
        fields["title"] = fields["title"].strip()
    for field, value in fields.items():
        setattr(defect, field, value)
    await write_audit_log(
        db,
        action="defect_update",
        resource_type="defect",
        resource_id=defect.id,
        user_id=user.id,
        username=user.username,
        project_id=defect.project_id,
        detail=f"更新内部缺陷: {defect.id}",
    )
    await db.commit()
    return _serialize_defect(await _load_defect_after_write(db, defect.id))


@router.post("/defects/{defect_id}/links", response_model=DefectRunLinkOut)
async def link_defect_run(
    defect_id: int,
    body: DefectRunLinkCreate,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    defect = await _get_defect(db, defect_id, user, ProjectRole.editor)
    link = await _attach_link(db, defect, body.run_type, body.run_id, user.id, body.case_id)
    await write_audit_log(
        db,
        action="defect_run_link",
        resource_type="defect",
        resource_id=defect.id,
        user_id=user.id,
        username=user.username,
        project_id=defect.project_id,
        detail=f"关联执行记录: {body.run_type}:{body.run_id}",
    )
    await db.commit()
    return _serialize_link(link)


@router.delete("/defects/{defect_id}/links/{link_id}", status_code=status.HTTP_204_NO_CONTENT)
async def unlink_defect_run(
    defect_id: int,
    link_id: int,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    defect = await _get_defect(db, defect_id, user, ProjectRole.editor)
    link = next((item for item in defect.run_links if item.id == link_id), None)
    if link is None:
        raise HTTPException(status_code=404, detail="缺陷执行关联不存在")
    await db.delete(link)
    await write_audit_log(
        db,
        action="defect_run_unlink",
        resource_type="defect",
        resource_id=defect.id,
        user_id=user.id,
        username=user.username,
        project_id=defect.project_id,
        detail=f"解除执行记录关联: {link.run_type}:{link.run_id}",
    )
    await db.commit()
