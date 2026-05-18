"""cases 包 - 审批工作流 + 快照/回滚。"""
from __future__ import annotations

import copy
from datetime import datetime, timezone

import app.api.v1.cases as _cases
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.core.database import get_db
from app.models.case import CaseSnapshot, CaseStatus, CaseType
from app.models.user import User
from app.schemas.case import (
    CaseSnapshotOut,
    CaseWorkflowRequest,
    PaginatedSnapshotsOut,
    TestCaseDetailOut,
)

router = APIRouter(tags=["用例管理"])


@router.post("/cases/{case_id}/submit-review", response_model=TestCaseDetailOut)
async def submit_review(
    case_id: int,
    body: CaseWorkflowRequest,
    db: AsyncSession = Depends(get_db),
    _current_user: User = Depends(get_current_user),
):
    case = await _cases._get_case_detail_or_404(db, case_id)
    if case.status == CaseStatus.deprecated:
        raise HTTPException(status_code=409, detail="废弃用例不能提交审核")
    case.review_status = "pending"
    case.submitted_at = datetime.now(timezone.utc)
    case.reviewed_at = None
    case.reviewed_by = None
    case.review_comment = body.comment
    await db.commit()
    return await _cases._get_case_detail_or_404(db, case_id)


@router.post("/cases/{case_id}/approve", response_model=TestCaseDetailOut)
async def approve_case(
    case_id: int,
    body: CaseWorkflowRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    case = await _cases._get_case_detail_or_404(db, case_id)
    if case.review_status != "pending":
        raise HTTPException(status_code=409, detail="只有待审核用例可批准")
    if case.status == CaseStatus.deprecated:
        raise HTTPException(status_code=409, detail="废弃用例不能批准")
    case.review_status = "approved"
    case.status = CaseStatus.active
    case.reviewed_at = datetime.now(timezone.utc)
    case.reviewed_by = current_user.id
    case.review_comment = body.comment
    await db.commit()
    return await _cases._get_case_detail_or_404(db, case_id)


@router.post("/cases/{case_id}/reject", response_model=TestCaseDetailOut)
async def reject_case(
    case_id: int,
    body: CaseWorkflowRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    case = await _cases._get_case_detail_or_404(db, case_id)
    if case.review_status != "pending":
        raise HTTPException(status_code=409, detail="只有待审核用例可驳回")
    case.review_status = "rejected"
    case.status = CaseStatus.draft
    case.reviewed_at = datetime.now(timezone.utc)
    case.reviewed_by = current_user.id
    case.review_comment = body.comment
    await db.commit()
    return await _cases._get_case_detail_or_404(db, case_id)


@router.post("/cases/{case_id}/deprecate", response_model=TestCaseDetailOut)
async def deprecate_case(
    case_id: int,
    body: CaseWorkflowRequest,
    db: AsyncSession = Depends(get_db),
    _current_user: User = Depends(get_current_user),
):
    case = await _cases._get_case_detail_or_404(db, case_id)
    if case.status == CaseStatus.deprecated:
        raise HTTPException(status_code=409, detail="用例已经废弃")
    case.status = CaseStatus.deprecated
    case.review_comment = body.comment or case.review_comment
    await db.commit()
    return await _cases._get_case_detail_or_404(db, case_id)


@router.post("/cases/{case_id}/reactivate", response_model=TestCaseDetailOut)
async def reactivate_case(
    case_id: int,
    body: CaseWorkflowRequest,
    db: AsyncSession = Depends(get_db),
    _current_user: User = Depends(get_current_user),
):
    case = await _cases._get_case_detail_or_404(db, case_id)
    if case.status != CaseStatus.deprecated:
        raise HTTPException(status_code=409, detail="只有废弃用例可重新激活")
    if case.review_status != "approved":
        raise HTTPException(status_code=409, detail="仅审核通过的用例可重新激活")
    case.status = CaseStatus.active
    case.review_comment = body.comment or case.review_comment
    await db.commit()
    return await _cases._get_case_detail_or_404(db, case_id)


@router.get("/cases/{case_id}/snapshots", response_model=PaginatedSnapshotsOut)
async def list_snapshots(
    case_id: int,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    _=Depends(get_current_user),
):
    await _cases._get_case_detail_or_404(db, case_id)
    total = await db.scalar(
        select(func.count()).select_from(
            select(CaseSnapshot.id).where(CaseSnapshot.case_id == case_id).subquery()
        )
    )
    result = await db.execute(
        select(CaseSnapshot, User.username)
        .outerjoin(User, CaseSnapshot.updated_by == User.id)
        .where(CaseSnapshot.case_id == case_id)
        .order_by(CaseSnapshot.version.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    items = []
    for snapshot, username in result.all():
        out = CaseSnapshotOut.model_validate(snapshot)
        out.updated_by_name = username or ""
        items.append(out)
    return PaginatedSnapshotsOut(items=items, total=total or 0, page=page, page_size=page_size)


@router.get("/cases/{case_id}/snapshots/{snapshot_id}", response_model=CaseSnapshotOut)
async def get_snapshot(
    case_id: int,
    snapshot_id: int,
    db: AsyncSession = Depends(get_db),
    _=Depends(get_current_user),
):
    snapshot = await db.get(CaseSnapshot, snapshot_id)
    if not snapshot or snapshot.case_id != case_id:
        raise HTTPException(status_code=404, detail="快照不存在")
    return snapshot


@router.post("/cases/{case_id}/rollback/{snapshot_id}", response_model=TestCaseDetailOut)
async def rollback_case(
    case_id: int,
    snapshot_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    case = await _cases._get_case_detail_or_404(db, case_id)
    snapshot = await db.get(CaseSnapshot, snapshot_id)
    if not snapshot or snapshot.case_id != case_id:
        raise HTTPException(status_code=404, detail="快照不存在")

    db.add(_cases._build_snapshot(case, await _cases._next_snapshot_version(db, case_id), current_user.id))

    data = snapshot.snapshot_data or {}
    case.name = data.get("name", snapshot.name)
    case.description = data.get("description", snapshot.description)
    case.summary = data.get("summary", case.name)
    case.case_type = CaseType(data.get("case_type", case.case_type.value))
    case.status = CaseStatus(data.get("status", case.status.value))
    case.priority = data.get("priority", case.priority)
    case.case_level = data.get("case_level", case.case_level)
    case.review_status = data.get("review_status", case.review_status)
    case.automation_status = data.get("automation_status", case.automation_status)
    case.owner_id = data.get("owner_id", case.owner_id)
    case.preconditions = _cases._normalize_string_list(data.get("preconditions", []))
    case.postconditions = _cases._normalize_string_list(data.get("postconditions", []))
    case.tags = _cases._normalize_string_list(data.get("tags", snapshot.tags or []))
    case.config = copy.deepcopy(data.get("config", snapshot.config or {}))
    await _cases._replace_case_steps(
        db,
        case,
        data.get("steps") or _cases._derive_steps_from_config(case.case_type, case.config, case.name),
    )
    await db.commit()
    return await _cases._get_case_detail_or_404(db, case_id)
