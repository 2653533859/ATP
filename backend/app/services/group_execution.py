"""Shared cooperative cancellation and read-only recovery explanations."""

from datetime import datetime, timedelta, timezone
import hashlib
from typing import Any, Literal

from sqlalchemy import bindparam, func, select, text, update, or_
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.execution_run_lease import ExecutionRunLease
from app.models.group_run_child import GroupRunChild
from app.models.plan import PlanRun, TestPlan
from app.models.suite import SuiteRun, TestSuite
from app.core.config import settings
from app.schemas.group_execution import GroupChildState, GroupExecutionState
from app.schemas.execution_dispatch import ExecutionDispatchOut
from app.services.execution_dispatch import get_suite_dispatch

GroupKind = Literal["suite", "plan"]


def group_revision(kind: GroupKind, run: Any) -> str:
    return hashlib.sha256(f"{kind}:{run.identity_token}".encode()).hexdigest()


def created_identity(value: Any) -> str:
    # Retain the raw SQLite timestamp; PostgreSQL returns an aware datetime.
    return _utc(value).isoformat() if isinstance(value, datetime) else str(value)


async def record_child(db: AsyncSession, *, kind: GroupKind, parent: Any, child: Any) -> None:
    table = "test_runs" if kind == "suite" else "suite_runs"
    child_identity = (
        child.identity_token
        if kind == "plan"
        else created_identity(
            (await db.execute(text(f"SELECT created_at FROM {table} WHERE id=:id"), {"id": child.id})).scalar_one()
        )
    )
    db.add(
        GroupRunChild(
            parent_kind=kind,
            parent_run_id=parent.id,
            parent_identity=parent.identity_token,
            child_kind="case" if kind == "suite" else "suite",
            child_id=child.id,
            child_identity=child_identity,
        )
    )


async def request_cancel(db: AsyncSession, kind: GroupKind, run: Any) -> bool:
    model: Any = SuiteRun if kind == "suite" else PlanRun
    now = datetime.now(timezone.utc)
    pending_result = await db.execute(
        update(model)
        .where(model.id == run.id, model.identity_token == run.identity_token, model.status == "pending")
        .values(
            cancel_requested_at=func.coalesce(model.cancel_requested_at, now),
            status="error",
            error_message="用户取消了排队执行；未继续启动子任务",
        )
        .execution_options(synchronize_session=False)
    )
    if getattr(pending_result, "rowcount", 0) == 1:
        await db.refresh(run)
        return True
    result = await db.execute(
        update(model)
        .where(model.id == run.id, model.identity_token == run.identity_token, model.status == "running")
        .values(cancel_requested_at=func.coalesce(model.cancel_requested_at, now))
        .execution_options(synchronize_session=False)
    )
    if getattr(result, "rowcount", 0) != 1:
        if run.cancel_requested_at is not None:
            return False
        raise ValueError("运行已经结束或身份变化")
    await db.refresh(run)
    return False


async def execution_state(
    db: AsyncSession,
    kind: GroupKind,
    run: Any,
    *,
    limit: int = 200,
    cursor: int | None = None,
    offset: int = 0,
) -> GroupExecutionState:
    owner_model: Any = TestSuite if kind == "suite" else TestPlan
    owner_id = run.suite_id if kind == "suite" else run.plan_id
    project_id = await db.scalar(select(owner_model.project_id).where(owner_model.id == owner_id))
    dispatch = await get_suite_dispatch(db, run) if kind == "suite" else None
    now = datetime.now(timezone.utc)
    lease = await db.scalar(
        select(ExecutionRunLease).where(
            ExecutionRunLease.task_type == kind,
            ExecutionRunLease.run_id == run.id,
            ExecutionRunLease.run_identity == run.identity_token,
        )
    )
    # Inline plan suites are owned by their parent's lease, not a separate task.
    if lease is None and kind == "suite":
        parent_link = await db.scalar(
            select(GroupRunChild).where(
                GroupRunChild.child_kind == "suite",
                GroupRunChild.child_id == run.id,
                GroupRunChild.child_identity == run.identity_token,
                GroupRunChild.parent_kind == "plan",
            )
        )
        if parent_link is not None:
            lease = await db.scalar(
                select(ExecutionRunLease)
                .join(PlanRun, PlanRun.id == ExecutionRunLease.run_id)
                .where(
                    ExecutionRunLease.task_type == "plan",
                    PlanRun.id == parent_link.parent_run_id,
                    PlanRun.identity_token == parent_link.parent_identity,
                    ExecutionRunLease.run_identity == parent_link.parent_identity,
                    PlanRun.status == "running",
                    PlanRun.plan_id.in_(select(TestPlan.id).where(TestPlan.project_id == project_id)),
                )
            )
    child_filter = (
        GroupRunChild.parent_kind == kind,
        GroupRunChild.parent_run_id == run.id,
        GroupRunChild.parent_identity == run.identity_token,
    )
    total = int((await db.scalar(select(func.count()).select_from(GroupRunChild).where(*child_filter))) or 0)
    ref_query = select(GroupRunChild).where(*child_filter)
    if cursor is not None:
        ref_query = ref_query.where(GroupRunChild.id > cursor)
    elif offset > 0:
        ref_query = ref_query.offset(offset)
    refs = (await db.scalars(ref_query.order_by(GroupRunChild.id).limit(limit))).all()
    # 按 child_kind 批量取回子任务身份，避免恢复面板轮询时的逐行 N+1 查询。
    case_refs = [ref for ref in refs if ref.child_kind == "case"]
    suite_refs = [ref for ref in refs if ref.child_kind != "case"]
    case_rows: dict[int, Any] = {}
    if case_refs:
        rows = (
            await db.execute(
                text(
                    "SELECT r.id, r.created_at, r.status FROM test_runs r JOIN test_cases c ON c.id=r.case_id "
                    "JOIN modules m ON m.id=c.module_id WHERE r.id IN :ids AND m.project_id=:project"
                ).bindparams(bindparam("ids", expanding=True)),
                {"ids": [ref.child_id for ref in case_refs], "project": project_id},
            )
        ).all()
        case_rows = {row[0]: row for row in rows}
    suite_rows: dict[int, Any] = {}
    if suite_refs:
        rows = (
            await db.execute(
                text(
                    "SELECT r.id, r.identity_token, r.status FROM suite_runs r JOIN test_suites s ON s.id=r.suite_id "
                    "WHERE r.id IN :ids AND s.project_id=:project"
                ).bindparams(bindparam("ids", expanding=True)),
                {"ids": [ref.child_id for ref in suite_refs], "project": project_id},
            )
        ).all()
        suite_rows = {row[0]: row for row in rows}
    children = []
    for ref in refs:
        if ref.child_kind == "case":
            row = case_rows.get(ref.child_id)
            verified = row is not None and created_identity(row[1]) == ref.child_identity
        else:
            row = suite_rows.get(ref.child_id)
            verified = row is not None and row[1] == ref.child_identity
        children.append(
            GroupChildState(
                kind=ref.child_kind,
                run_id=ref.child_id,
                verified=verified,
                status=str(row[2]) if verified and row else None,
            )
        )
    status = run.status.value
    verified_cases = [child.run_id for child in children if child.verified and child.kind == "case"]
    verified_suites = {child.run_id for child in children if child.verified and child.kind == "suite"}
    suite_lease_matches = [
        (ExecutionRunLease.run_id == ref.child_id) & (ExecutionRunLease.run_identity == ref.child_identity)
        for ref in refs
        if ref.child_kind == "suite" and ref.child_id in verified_suites
    ]
    unresolved_leases = (
        await db.scalars(
            select(ExecutionRunLease).where(
                ExecutionRunLease.status.in_(["active", "expired"]),
                or_(
                    (ExecutionRunLease.task_type == "case") & ExecutionRunLease.run_id.in_(verified_cases),
                    # Numeric IDs may be reused. A predecessor's lease cannot
                    # make the replacement child's terminal result uncertain.
                    (ExecutionRunLease.task_type == "suite") & or_(False, *suite_lease_matches),
                ),
            )
        )
    ).all()
    unresolved = {(lease.task_type, lease.run_id) for lease in unresolved_leases}
    for child in children:
        child.execution_uncertain = (
            child.verified and child.status not in {"pending", "running"} and (child.kind, child.run_id) in unresolved
        )
    reason = "terminal" if status not in {"pending", "running"} else "legacy_pending"
    reconcile = False
    if status == "running":
        live = lease is not None and lease.status == "active" and _utc(lease.expires_at) > now
        reason, reconcile = ("running", False) if live else ("worker_unverified", True)
    elif status == "pending" and dispatch is not None:
        if dispatch.accepted_at is not None:
            stalled = now - _utc(dispatch.accepted_at) > timedelta(minutes=5)
            reason, reconcile = ("accepted_stalled", True) if stalled else ("accepted_waiting", False)
        else:
            reason = {
                "pending": "waiting_dispatch",
                "publishing": "dispatching",
                "submitted": "queued",
                "uncertain": "dispatch_uncertain",
                "blocked": "dispatch_blocked",
                "skipped": "dispatch_skipped",
            }.get(dispatch.status, "dispatch_blocked")
            reconcile = dispatch.status not in {"pending", "publishing", "submitted"}
    if status == "error" and lease is not None and lease.status == "expired":
        reason, reconcile = "worker_unverified", True
    if settings.ATP_LOCAL_MODE and status == "error":
        job_status = (
            await db.execute(
                text(
                    "SELECT status FROM local_jobs WHERE task_name=:task AND run_id=:id AND run_identity=:identity "
                    "ORDER BY id DESC LIMIT 1"
                ),
                {
                    "task": "run_test_suite" if kind == "suite" else "run_test_plan",
                    "id": run.id,
                    "identity": run.identity_token,
                },
            )
        ).scalar_one_or_none()
        if job_status in {"interrupted", "failed"}:
            reason, reconcile = "execution_interrupted", True
    if run.cancel_requested_at is not None:
        reason = "cancelled" if status not in {"pending", "running"} else "cancelling"
    if status not in {"pending", "running"} and any(
        c.verified and c.status in {"pending", "running"} for c in children
    ):
        reason, reconcile = "children_unfinished", True
    recorded_ids = {ref.child_id for ref in refs}
    old_refs = run.case_run_ids if kind == "suite" else run.suite_run_ids
    key = "run_id" if kind == "suite" else "suite_run_id"
    legacy = (
        any(isinstance(item, dict) and item.get(key) and item[key] not in recorded_ids for item in (old_refs or []))
        if total <= 200
        else False
    )
    if any(not c.verified for c in children):
        reason, reconcile = "child_identity_unverified", True
    if any(c.execution_uncertain for c in children):
        reason, reconcile = "child_execution_uncertain", True
    if status not in {"pending", "running"} and total > len(children) and not reconcile:
        # Remaining children lie outside the bounded response and cannot be verified.
        reason, reconcile = "children_truncated", True
    active_count = sum(1 for c in children if c.verified and c.status in {"pending", "running"})
    terminal_count = sum(1 for c in children if c.verified and c.status not in {"pending", "running", None})
    has_more = (
        (offset + len(refs)) < total
        if cursor is None
        else (len(refs) == limit and ((offset + len(refs)) < total or total > len(refs)))
    )
    next_cursor = refs[-1].id if refs and has_more else None

    return GroupExecutionState(
        kind=kind,
        run_id=run.id,
        revision=group_revision(kind, run),
        run_status=status,
        reason=reason,
        requires_reconciliation=reconcile,
        cancel_requested_at=run.cancel_requested_at,
        can_cancel=status in {"pending", "running"} and run.cancel_requested_at is None,
        dispatch=ExecutionDispatchOut.model_validate(dispatch) if dispatch else None,
        lease_status=lease.status if lease else None,
        lease_expires_at=lease.expires_at if lease else None,
        children=children,
        child_count=total,
        children_truncated=total > len(children),
        legacy_children_unverified=legacy,
        next_cursor=next_cursor,
        has_more=has_more,
        active_children_count=active_count,
        terminal_children_count=terminal_count,
    )


def _utc(value: datetime) -> datetime:
    return value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value.astimezone(timezone.utc)
