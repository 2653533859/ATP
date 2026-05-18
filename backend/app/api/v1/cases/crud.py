"""cases 包 - CRUD 端点（list / create / get / update / copy / delete）。

可被 monkeypatch 的符号（write_audit_log / invalidate_stats_cache /
_get_case_detail_or_404 等）通过 ``app.api.v1.cases`` 模块访问，确保
``monkeypatch.setattr(cases, "X", fake)`` 仍能生效。
"""
from __future__ import annotations

import copy

import app.api.v1.cases as _cases
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.core.database import get_db
from app.models.case import CaseStatus, TestCase
from app.models.project import Module
from app.models.user import User
from app.schemas.case import TestCaseCreate, TestCaseDetailOut, TestCaseOut, TestCaseUpdate

router = APIRouter(tags=["用例管理"])


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
    _=Depends(get_current_user),
):
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
    return items


@router.post("/cases", response_model=TestCaseDetailOut, status_code=status.HTTP_201_CREATED)
async def create_case(
    body: TestCaseCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    module = await _cases._get_module_for_case_code(db, body.module_id)
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
    await db.commit()
    return case


@router.get("/cases/{case_id}", response_model=TestCaseDetailOut)
async def get_case(case_id: int, db: AsyncSession = Depends(get_db), _=Depends(get_current_user)):
    return await _cases._get_case_detail_or_404(db, case_id)


@router.patch("/cases/{case_id}", response_model=TestCaseDetailOut)
async def update_case(
    case_id: int,
    body: TestCaseUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    case = await _cases._get_case_detail_or_404(db, case_id)
    db.add(_cases._build_snapshot(case, await _cases._next_snapshot_version(db, case_id), current_user.id))

    payload = body.model_dump(exclude_none=True)
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

    if "steps" in payload:
        await _cases._replace_case_steps(
            db,
            case,
            _cases._normalize_steps(payload["steps"] or [], case.case_type, case.config or {}, payload.get("name") or case.name),
        )
    elif "config" in payload:
        await _cases._replace_case_steps(db, case, _cases._normalize_steps([], case.case_type, case.config or {}, case.name))

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
