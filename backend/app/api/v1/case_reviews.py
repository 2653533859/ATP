"""Project-aware review queue, batch decisions, and review history."""

from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import assert_project_access, get_current_user
from app.core.database import get_db
from app.models.audit import AuditLog
from app.models.case import CaseSnapshot, CaseStatus, CaseStep, TestCase
from app.models.project import Module, Project
from app.models.user import User
from app.models.user_project import ProjectRole
from app.schemas.case_review import (
    CaseReviewBatchIn,
    CaseReviewBatchOut,
    CaseReviewCounts,
    CaseReviewHistoryItem,
    CaseReviewQueueItem,
    CaseReviewQueueOut,
)
from app.services.audit import write_audit_log
from app.services.case_review import build_review_audit_detail, parse_review_audit_detail
from app.services.project_scope import scope_to_visible_projects

router = APIRouter(tags=["用例评审"])

_REVIEW_STATUSES = {"all", "pending", "approved", "rejected"}
_REVIEW_AUDIT_ACTIONS = {"case_review_submit", "case_review_approve", "case_review_reject"}


def _case_filters(project_id: int | None, module_id: int | None, keyword: str | None) -> list:
    filters = []
    if module_id is not None:
        filters.append(TestCase.module_id == module_id)
    if keyword and keyword.strip():
        like_keyword = f"%{keyword.strip()}%"
        filters.append(
            (TestCase.name.ilike(like_keyword))
            | (TestCase.case_code.ilike(like_keyword))
            | (TestCase.summary.ilike(like_keyword))
        )
    return filters


async def _assert_project_filter_access(db: AsyncSession, user: User, project_id: int | None) -> None:
    if project_id is not None:
        await assert_project_access(db, user, project_id, ProjectRole.viewer)


def _review_queue_query(*, project_id: int | None, module_id: int | None, keyword: str | None, user: User):
    step_count = (
        select(func.count(CaseStep.id)).where(CaseStep.case_id == TestCase.id).correlate(TestCase).scalar_subquery()
    )
    snapshot_count = (
        select(func.count(CaseSnapshot.id))
        .where(CaseSnapshot.case_id == TestCase.id)
        .correlate(TestCase)
        .scalar_subquery()
    )
    latest_snapshot_version = (
        select(func.max(CaseSnapshot.version))
        .where(CaseSnapshot.case_id == TestCase.id)
        .correlate(TestCase)
        .scalar_subquery()
    )
    statement = (
        select(
            TestCase,
            Project.id,
            Project.name,
            Module.id,
            Module.name,
            User.username,
            step_count,
            snapshot_count,
            latest_snapshot_version,
        )
        .join(Module, TestCase.module_id == Module.id)
        .join(Project, Module.project_id == Project.id)
        .outerjoin(User, TestCase.reviewed_by == User.id)
    )
    statement = scope_to_visible_projects(statement, Module.project_id, user, project_id)
    return statement.where(*_case_filters(project_id, module_id, keyword))


def _queue_item(row) -> CaseReviewQueueItem:
    (
        case,
        project_id,
        project_name,
        module_id,
        module_name,
        reviewer_name,
        step_count,
        snapshot_count,
        latest_version,
    ) = row
    case_type = getattr(case.case_type, "value", case.case_type)
    return CaseReviewQueueItem(
        id=case.id,
        project_id=project_id,
        project_name=project_name,
        module_id=module_id,
        module_name=module_name,
        name=case.name,
        case_code=case.case_code,
        summary=case.summary,
        case_type=str(case_type),
        priority=case.priority,
        case_level=case.case_level,
        review_status=case.review_status,
        automation_status=case.automation_status,
        creator_id=case.creator_id,
        owner_id=case.owner_id,
        submitted_at=case.submitted_at,
        reviewed_at=case.reviewed_at,
        reviewed_by=case.reviewed_by,
        reviewer_name=reviewer_name,
        review_comment=case.review_comment,
        step_count=int(step_count or 0),
        snapshot_count=int(snapshot_count or 0),
        latest_snapshot_version=int(latest_version) if latest_version is not None else None,
        created_at=case.created_at,
        updated_at=case.updated_at,
    )


@router.get("/case-reviews", response_model=CaseReviewQueueOut)
async def list_case_reviews(
    project_id: int | None = Query(default=None, ge=1),
    module_id: int | None = Query(default=None, ge=1),
    review_status: str = Query(default="pending"),
    keyword: str | None = Query(default=None, max_length=128),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=50, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    if review_status not in _REVIEW_STATUSES:
        raise HTTPException(status_code=422, detail="review_status 必须为 all、pending、approved 或 rejected")
    await _assert_project_filter_access(db, user, project_id)

    base = _review_queue_query(project_id=project_id, module_id=module_id, keyword=keyword, user=user)
    count_query = (
        select(TestCase.review_status, func.count(TestCase.id))
        .join(Module, TestCase.module_id == Module.id)
        .group_by(TestCase.review_status)
    )
    count_query = scope_to_visible_projects(count_query, Module.project_id, user, project_id)
    count_rows = (await db.execute(count_query.where(*_case_filters(project_id, module_id, keyword)))).all()
    counts_map = {str(status): int(count) for status, count in count_rows}
    counts = CaseReviewCounts(
        all=sum(counts_map.values()),
        pending=counts_map.get("pending", 0),
        approved=counts_map.get("approved", 0),
        rejected=counts_map.get("rejected", 0),
    )

    if review_status != "all":
        base = base.where(TestCase.review_status == review_status)
    rows = (
        await db.execute(
            base.order_by(TestCase.submitted_at.desc().nullslast(), TestCase.updated_at.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
    ).all()
    total = counts_map.get(review_status, counts.all) if review_status != "all" else counts.all
    return CaseReviewQueueOut(
        items=[_queue_item(row) for row in rows],
        total=total,
        page=page,
        page_size=page_size,
        counts=counts,
    )


@router.post("/case-reviews/batch", response_model=CaseReviewBatchOut)
async def batch_review_cases(
    body: CaseReviewBatchIn,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    requested_ids = list(dict.fromkeys(body.case_ids))
    rows = (
        await db.execute(
            select(TestCase, Module.project_id)
            .join(Module, TestCase.module_id == Module.id)
            .where(TestCase.id.in_(requested_ids))
            .with_for_update()
        )
    ).all()
    for project_id in {project_id for _, project_id in rows}:
        await assert_project_access(db, current_user, project_id, ProjectRole.editor)

    found_ids = {case.id for case, _ in rows}
    skipped_ids = [case_id for case_id in requested_ids if case_id not in found_ids]
    processed_ids: list[int] = []
    now = datetime.now(timezone.utc)
    target_status = "approved" if body.action == "approve" else "rejected"
    target_case_status = CaseStatus.active if body.action == "approve" else CaseStatus.draft
    audit_action = f"case_review_{body.action}"

    for case, project_id in rows:
        if case.review_status != "pending" or case.status == CaseStatus.deprecated:
            skipped_ids.append(case.id)
            continue
        case.review_status = target_status
        case.status = target_case_status
        case.reviewed_at = now
        case.reviewed_by = current_user.id
        case.review_comment = body.comment
        processed_ids.append(case.id)
        await write_audit_log(
            db,
            action=audit_action,
            resource_type="test_case",
            resource_id=case.id,
            user_id=current_user.id,
            username=getattr(current_user, "username", ""),
            project_id=project_id,
            detail=build_review_audit_detail(
                action=body.action,
                status=target_status,
                comment=body.comment,
                source="workbench",
            ),
        )

    await db.commit()
    return CaseReviewBatchOut(
        requested=len(requested_ids),
        processed=len(processed_ids),
        processed_ids=processed_ids,
        skipped_ids=[case_id for case_id in requested_ids if case_id in set(skipped_ids)],
    )


@router.get("/case-reviews/{case_id}/history", response_model=list[CaseReviewHistoryItem])
async def list_case_review_history(
    case_id: int,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    row = (
        await db.execute(
            select(TestCase, Module.project_id)
            .join(Module, TestCase.module_id == Module.id)
            .where(TestCase.id == case_id)
        )
    ).one_or_none()
    if row is None:
        raise HTTPException(status_code=404, detail="用例不存在")
    case, project_id = row
    await assert_project_access(db, user, project_id, ProjectRole.viewer)

    audit_rows = (
        (
            await db.execute(
                select(AuditLog)
                .where(
                    AuditLog.resource_type == "test_case",
                    AuditLog.resource_id == case_id,
                    AuditLog.action.in_(_REVIEW_AUDIT_ACTIONS),
                )
                .order_by(AuditLog.created_at.desc(), AuditLog.id.desc())
                .limit(100)
            )
        )
        .scalars()
        .all()
    )
    history = []
    for log in audit_rows:
        data = parse_review_audit_detail(log.detail)
        action = str(data.get("action") or log.action.removeprefix("case_review_"))
        history.append(
            CaseReviewHistoryItem(
                id=log.id,
                case_id=case_id,
                action=action,
                status=str(data.get("status") or "unknown"),
                comment=data.get("comment") if isinstance(data.get("comment"), str) else None,
                reviewer_id=log.user_id,
                reviewer_name=log.username or "",
                source=str(data.get("source") or "case"),
                created_at=log.created_at,
            )
        )
    if history:
        return history

    snapshots = (
        await db.execute(
            select(CaseSnapshot, User.username)
            .outerjoin(User, CaseSnapshot.updated_by == User.id)
            .where(CaseSnapshot.case_id == case_id)
            .order_by(CaseSnapshot.created_at.desc(), CaseSnapshot.id.desc())
            .limit(100)
        )
    ).all()
    for snapshot, username in snapshots:
        status = str((snapshot.snapshot_data or {}).get("review_status") or "")
        if status not in {"pending", "approved", "rejected"}:
            continue
        history.append(
            CaseReviewHistoryItem(
                id=snapshot.id,
                case_id=case_id,
                action="snapshot",
                status=status,
                comment=None,
                reviewer_id=snapshot.updated_by,
                reviewer_name=username or "",
                source="snapshot",
                snapshot_version=snapshot.version,
                created_at=snapshot.created_at,
            )
        )
    return history
