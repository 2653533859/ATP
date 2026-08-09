"""cases 包 - CRUD 端点（list / create / get / update / copy / delete）。

可被 monkeypatch 的符号（write_audit_log / invalidate_stats_cache /
_get_case_detail_or_404 等）通过 ``app.api.v1.cases`` 模块访问，确保
``monkeypatch.setattr(cases, "X", fake)`` 仍能生效。
"""

from __future__ import annotations

import copy
import json

import app.api.v1.cases as _cases
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import assert_project_access, get_current_user
from app.core.database import get_db
from app.models.case import CaseStatus, RunStatus, TestCase, TestRun
from app.models.dataset import TestDataset, TestDatasetVersion
from app.models.project import Module
from app.models.user import User
from app.models.user_project import ProjectRole
from app.schemas.case import TestCaseCreate, TestCaseDetailOut, TestCaseOut, TestCaseUpdate

router = APIRouter(tags=["用例管理"])

FLAKY_WINDOW_SIZE = 10
FLAKY_MIN_RUNS = 4
FLAKY_TERMINAL_STATUSES = (RunStatus.passed, RunStatus.failed, RunStatus.error)


async def _resolve_dataset_binding(
    db: AsyncSession,
    dataset_id: int | None,
    dataset_version: int | None,
    project_id: int,
) -> tuple[int | None, int | None]:
    """Validate a case dataset and preserve an explicitly requested immutable version."""
    if dataset_id is None:
        if dataset_version is not None:
            raise HTTPException(status_code=400, detail="数据集版本必须依赖数据集")
        return None, None

    dataset = await db.get(TestDataset, dataset_id)
    if dataset is None:
        raise HTTPException(status_code=404, detail="测试数据集不存在")
    if dataset.project_id != project_id:
        raise HTTPException(status_code=400, detail="测试数据集不属于当前项目")
    if dataset_version is None:
        return dataset_id, None

    result = await db.execute(
        select(TestDatasetVersion)
        .where(
            TestDatasetVersion.dataset_id == dataset_id,
            TestDatasetVersion.version == dataset_version,
        )
        .limit(1)
    )
    version = result.scalar_one_or_none()
    if version is None:
        raise HTTPException(status_code=404, detail="测试数据集版本不存在")
    return dataset_id, int(version.version)


def _empty_flaky_stats() -> dict:
    return {
        "is_flaky": False,
        "total_runs": 0,
        "passed_runs": 0,
        "failed_runs": 0,
        "error_runs": 0,
        "failure_rate": 0.0,
        "window_size": FLAKY_WINDOW_SIZE,
    }


async def _attach_flaky_stats(db: AsyncSession, cases: list[TestCase]) -> None:
    case_ids = [case.id for case in cases]
    if not case_ids:
        return

    ranked = (
        select(
            TestRun.case_id.label("case_id"),
            TestRun.status.label("status"),
            func.row_number()
            .over(
                partition_by=TestRun.case_id,
                order_by=(TestRun.created_at.desc(), TestRun.id.desc()),
            )
            .label("rn"),
        )
        .where(
            TestRun.case_id.in_(case_ids),
            TestRun.status.in_(FLAKY_TERMINAL_STATUSES),
            TestRun.parent_run_id.is_(None),
        )
        .subquery()
    )
    rows = (await db.execute(select(ranked.c.case_id, ranked.c.status).where(ranked.c.rn <= FLAKY_WINDOW_SIZE))).all()

    stats_by_case = {case_id: _empty_flaky_stats() for case_id in case_ids}
    for row in rows:
        stats = stats_by_case[row.case_id]
        stats["total_runs"] += 1
        status = row.status.value if hasattr(row.status, "value") else str(row.status)
        if status == "passed":
            stats["passed_runs"] += 1
        elif status == "failed":
            stats["failed_runs"] += 1
        elif status == "error":
            stats["error_runs"] += 1

    for case in cases:
        stats = stats_by_case.get(case.id, _empty_flaky_stats())
        failure_runs = stats["failed_runs"] + stats["error_runs"]
        if stats["total_runs"]:
            stats["failure_rate"] = round(failure_runs / stats["total_runs"] * 100, 1)
        stats["is_flaky"] = stats["total_runs"] >= FLAKY_MIN_RUNS and stats["passed_runs"] > 0 and failure_runs > 0
        setattr(case, "flaky_stats", stats)


@router.get("/cases", response_model=list[TestCaseOut])
async def list_cases(
    project_id: int | None = None,
    module_id: int | None = None,
    case_type: str | None = None,
    priority: str | None = None,
    status: str | None = None,
    review_status: str | None = None,
    owner_id: int | None = None,
    automation_status: str | None = None,
    tag: str | None = None,
    keyword: str | None = None,
    db: AsyncSession = Depends(get_db),
    user=Depends(get_current_user),
):
    if project_id:
        await assert_project_access(db, user, project_id, ProjectRole.viewer)
    elif module_id:
        module = await db.get(Module, module_id)
        if module:
            await assert_project_access(db, user, module.project_id, ProjectRole.viewer)
    query = select(TestCase)
    if project_id:
        query = query.join(Module, TestCase.module_id == Module.id).where(Module.project_id == project_id)
    if module_id:
        query = query.where(TestCase.module_id == module_id)
    if case_type:
        query = query.where(TestCase.case_type == case_type)
    if priority:
        query = query.where(TestCase.priority == priority)
    if status:
        query = query.where(TestCase.status == status)
    if review_status:
        query = query.where(TestCase.review_status == review_status)
    if owner_id:
        query = query.where(TestCase.owner_id == owner_id)
    if automation_status:
        query = query.where(TestCase.automation_status == automation_status)
    if keyword:
        like_keyword = f"%{keyword.strip()}%"
        query = query.where(
            or_(
                TestCase.name.ilike(like_keyword),
                TestCase.summary.ilike(like_keyword),
                TestCase.case_code.ilike(like_keyword),
            )
        )
    result = await db.execute(query.order_by(TestCase.updated_at.desc(), TestCase.created_at.desc()))
    items = result.scalars().all()
    if tag:
        items = [case for case in items if tag in (case.tags or [])]
    await _attach_flaky_stats(db, items)
    return items


@router.post("/cases", response_model=TestCaseDetailOut, status_code=status.HTTP_201_CREATED)
async def create_case(
    body: TestCaseCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    module = await _cases._get_module_for_case_code(db, body.module_id)
    await assert_project_access(db, current_user, module.project_id, ProjectRole.editor)
    dataset_id, dataset_version = await _resolve_dataset_binding(
        db, body.dataset_id, body.dataset_version, module.project_id
    )
    steps_payload = _cases._normalize_steps(body.steps, body.case_type, body.config, body.name)
    case = TestCase(
        name=body.name,
        description=body.description,
        case_code=await _cases._generate_case_code(db, module, body.case_type),
        summary=body.summary or body.description or body.name,
        case_type=body.case_type,
        status=CaseStatus.draft,
        priority=body.priority,
        case_level=body.case_level,
        review_status="pending",
        automation_status=body.automation_status,
        tags=list(body.tags),
        module_id=body.module_id,
        creator_id=current_user.id,
        owner_id=body.owner_id or current_user.id,
        preconditions=list(body.preconditions),
        postconditions=list(body.postconditions),
        config=copy.deepcopy(body.config),
        dataset_id=dataset_id,
        dataset_version=dataset_version,
    )
    await _cases._replace_case_steps(db, case, steps_payload)
    db.add(case)
    await db.commit()
    await _cases.invalidate_stats_cache()
    case = await _cases._get_case_detail_or_404(db, case.id)
    await _cases.write_audit_log(
        db,
        action="create",
        resource_type="test_case",
        resource_id=case.id,
        user_id=current_user.id,
        username=getattr(current_user, "username", ""),
        detail=f"创建用例: {case.name}",
    )
    if isinstance(case.config, dict) and case.config.get("_ai_generated") is True:
        await _cases.write_audit_log(
            db,
            action="ai_case_draft_saved",
            resource_type="test_case",
            resource_id=case.id,
            user_id=current_user.id,
            username=getattr(current_user, "username", ""),
            project_id=module.project_id,
            detail=json.dumps(
                {
                    "project_id": module.project_id,
                    "module_id": body.module_id,
                    "case_id": case.id,
                    "saved_count": 1,
                },
                ensure_ascii=False,
            ),
        )
    await db.commit()
    return case


@router.get("/cases/{case_id}", response_model=TestCaseDetailOut)
async def get_case(case_id: int, db: AsyncSession = Depends(get_db), user=Depends(get_current_user)):
    case = await _cases._get_case_detail_or_404(db, case_id)
    module = await db.get(Module, case.module_id)
    if module:
        await assert_project_access(db, user, module.project_id, ProjectRole.viewer)
    await _attach_flaky_stats(db, [case])
    return case


@router.patch("/cases/{case_id}", response_model=TestCaseDetailOut)
async def update_case(
    case_id: int,
    body: TestCaseUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    case = await _cases._get_case_detail_or_404(db, case_id)
    module = await db.get(Module, case.module_id)
    if module:
        await assert_project_access(db, current_user, module.project_id, ProjectRole.editor)
    db.add(_cases._build_snapshot(case, await _cases._next_snapshot_version(db, case_id), current_user.id))
    await _cases._enforce_snapshot_retention(db, case_id)

    payload = body.model_dump(exclude_unset=True)
    if "name" in payload:
        case.name = payload["name"]
    if "description" in payload:
        case.description = payload["description"]
    if "summary" in payload:
        case.summary = payload["summary"] or case.name
    if "tags" in payload:
        case.tags = list(payload["tags"])
    if "preconditions" in payload:
        case.preconditions = list(payload["preconditions"])
    if "postconditions" in payload:
        case.postconditions = list(payload["postconditions"])
    if "priority" in payload:
        case.priority = payload["priority"]
    if "case_level" in payload:
        case.case_level = payload["case_level"]
    if "owner_id" in payload:
        case.owner_id = payload["owner_id"]
    if "automation_status" in payload:
        case.automation_status = payload["automation_status"]
    if "config" in payload:
        case.config = copy.deepcopy(payload["config"])
    if "dataset_id" in payload or "dataset_version" in payload:
        dataset_id, dataset_version = await _resolve_dataset_binding(
            db,
            payload.get("dataset_id", case.dataset_id),
            payload.get("dataset_version", case.dataset_version),
            module.project_id if module else 0,
        )
        case.dataset_id = dataset_id
        case.dataset_version = dataset_version

    if "steps" in payload:
        await _cases._replace_case_steps(
            db,
            case,
            _cases._normalize_steps(
                payload["steps"] or [], case.case_type, case.config or {}, payload.get("name") or case.name
            ),
        )
    elif "config" in payload:
        await _cases._replace_case_steps(
            db, case, _cases._normalize_steps([], case.case_type, case.config or {}, case.name)
        )

    if case.review_status == "approved":
        _cases._reset_review_after_edit(case)

    await db.commit()
    return await _cases._get_case_detail_or_404(db, case_id)


@router.post("/cases/{case_id}/copy", response_model=TestCaseDetailOut, status_code=status.HTTP_201_CREATED)
async def copy_case(
    case_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    source = await _cases._get_case_detail_or_404(db, case_id)
    module = await _cases._get_module_for_case_code(db, source.module_id)
    await assert_project_access(db, current_user, module.project_id, ProjectRole.editor)
    cloned = TestCase(
        name=f"{source.name} Copy",
        description=source.description,
        case_code=await _cases._generate_case_code(db, module, source.case_type),
        summary=source.summary,
        case_type=source.case_type,
        status=CaseStatus.draft,
        priority=source.priority,
        case_level=source.case_level,
        review_status="pending",
        automation_status=source.automation_status,
        tags=_cases._normalize_string_list(source.tags),
        module_id=source.module_id,
        creator_id=current_user.id,
        owner_id=current_user.id,
        preconditions=_cases._normalize_string_list(source.preconditions),
        postconditions=_cases._normalize_string_list(source.postconditions),
        config=copy.deepcopy(source.config or {}),
        dataset_id=source.dataset_id,
        dataset_version=source.dataset_version,
    )
    await _cases._replace_case_steps(db, cloned, _cases._serialize_steps(source.steps or []))
    db.add(cloned)
    await db.commit()
    await _cases.invalidate_stats_cache()
    return await _cases._get_case_detail_or_404(db, cloned.id)


@router.delete("/cases/{case_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_case(
    case_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    case = await db.get(TestCase, case_id)
    if not case:
        raise HTTPException(status_code=404, detail="用例不存在")
    module = await db.get(Module, case.module_id)
    if module:
        await assert_project_access(db, current_user, module.project_id, ProjectRole.editor)
    case_name = case.name
    await db.delete(case)
    await _cases.write_audit_log(
        db,
        action="delete",
        resource_type="test_case",
        resource_id=case_id,
        user_id=current_user.id,
        username=getattr(current_user, "username", ""),
        detail=f"删除用例: {case_name}",
    )
    await db.commit()
    await _cases.invalidate_stats_cache()
