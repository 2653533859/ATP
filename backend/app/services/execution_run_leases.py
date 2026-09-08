"""Worker-owned leases and lost-worker recovery for execution runs."""

from __future__ import annotations

import logging
import socket
import threading
import uuid
from contextlib import AbstractContextManager
from datetime import datetime, timedelta, timezone
from typing import Any

from sqlalchemy import select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.execution_run_lease import ExecutionRunLease

logger = logging.getLogger(__name__)

SUPPORTED_TASK_TYPES = frozenset({"case", "suite", "plan", "android", "performance"})
_LOST_WORKER_ERROR = "Execution worker heartbeat expired; the run was recovered as failed."


class ExecutionLeaseConflict(RuntimeError):
    """Raised when another live delivery already owns the same run."""


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _as_utc(value: datetime) -> datetime:
    return value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value.astimezone(timezone.utc)


def _validate_task_type(task_type: str) -> None:
    if task_type not in SUPPORTED_TASK_TYPES:
        raise ValueError(f"Unsupported execution lease task type: {task_type}")


def acquire_execution_run_lease(
    session: Session,
    *,
    task_type: str,
    run_id: int,
    lease_token: str,
    worker_id: str,
    celery_task_id: str | None,
    ttl_seconds: int,
    now: datetime | None = None,
) -> ExecutionRunLease:
    """Claim a run, rejecting a duplicate delivery while its lease is live."""
    _validate_task_type(task_type)
    current_time = now or _utcnow()
    lease = session.scalar(
        select(ExecutionRunLease)
        .where(ExecutionRunLease.task_type == task_type, ExecutionRunLease.run_id == run_id)
        .with_for_update()
    )
    if lease is not None:
        if lease.status == "active" and _as_utc(lease.expires_at) <= current_time:
            lease.status = "expired"
            lease.released_at = current_time
            lease.failure_reason = _LOST_WORKER_ERROR
            _recover_run(session, task_type, run_id)
            session.commit()
            raise ExecutionLeaseConflict(
                f"{task_type} run {run_id} has an expired lease; create a new run for an explicit retry"
            )
        raise ExecutionLeaseConflict(
            f"{task_type} run {run_id} already has a {lease.status} lease owned by {lease.worker_id}"
        )

    expires_at = current_time + timedelta(seconds=ttl_seconds)
    lease = ExecutionRunLease(
        task_type=task_type,
        run_id=run_id,
        lease_token=lease_token,
        worker_id=worker_id,
        celery_task_id=celery_task_id,
        status="active",
        acquired_at=current_time,
        heartbeat_at=current_time,
        expires_at=expires_at,
    )
    session.add(lease)
    try:
        session.commit()
    except IntegrityError as exc:
        session.rollback()
        winner = session.scalar(
            select(ExecutionRunLease).where(
                ExecutionRunLease.task_type == task_type,
                ExecutionRunLease.run_id == run_id,
            )
        )
        if winner is not None:
            raise ExecutionLeaseConflict(
                f"{task_type} run {run_id} already has a {winner.status} lease owned by {winner.worker_id}"
            ) from exc
        raise
    return lease


def heartbeat_execution_run_lease(
    session: Session,
    *,
    task_type: str,
    run_id: int,
    lease_token: str,
    ttl_seconds: int,
    now: datetime | None = None,
) -> bool:
    """Extend a lease only when the caller still owns its fencing token."""
    current_time = now or _utcnow()
    result = session.execute(
        update(ExecutionRunLease)
        .where(
            ExecutionRunLease.task_type == task_type,
            ExecutionRunLease.run_id == run_id,
            ExecutionRunLease.lease_token == lease_token,
            ExecutionRunLease.status == "active",
        )
        .values(
            heartbeat_at=current_time,
            expires_at=current_time + timedelta(seconds=ttl_seconds),
        )
        .execution_options(synchronize_session=False)
    )
    session.commit()
    return (result.rowcount or 0) == 1


def release_execution_run_lease(
    session: Session,
    *,
    task_type: str,
    run_id: int,
    lease_token: str,
    now: datetime | None = None,
) -> bool:
    """Release a lease only if its fencing token is still current."""
    current_time = now or _utcnow()
    result = session.execute(
        update(ExecutionRunLease)
        .where(
            ExecutionRunLease.task_type == task_type,
            ExecutionRunLease.run_id == run_id,
            ExecutionRunLease.lease_token == lease_token,
            ExecutionRunLease.status == "active",
        )
        .values(status="released", released_at=current_time, expires_at=current_time)
        .execution_options(synchronize_session=False)
    )
    session.commit()
    return (result.rowcount or 0) == 1


def _recover_run(session: Session, task_type: str, run_id: int, *, force: bool = False) -> bool:
    """Move one domain run to its safe terminal state."""
    now = _utcnow()
    if task_type == "case":
        from app.models.case import RunStatus, TestRun

        case_run = session.get(TestRun, run_id)
        case_active = {RunStatus.pending, RunStatus.running}
        if case_run is None or (not force and case_run.status not in case_active):
            return False
        case_run.status = RunStatus.error
        case_run.error_message = _LOST_WORKER_ERROR
    elif task_type == "suite":
        from app.models.suite import SuiteRun, SuiteRunStatus

        suite_run = session.get(SuiteRun, run_id)
        suite_active = {SuiteRunStatus.pending, SuiteRunStatus.running}
        if suite_run is None or (not force and suite_run.status not in suite_active):
            return False
        suite_run.status = SuiteRunStatus.error
        suite_run.error_message = _LOST_WORKER_ERROR
    elif task_type == "plan":
        from app.models.plan import PlanRun, PlanRunStatus

        plan_run = session.get(PlanRun, run_id)
        plan_active = {PlanRunStatus.pending, PlanRunStatus.running}
        if plan_run is None or (not force and plan_run.status not in plan_active):
            return False
        plan_run.status = PlanRunStatus.error
        plan_run.error_message = _LOST_WORKER_ERROR
    elif task_type == "android":
        from app.models.mobile_special import MobileSpecialRun, RunStatus as MobileRunStatus

        mobile_run = session.get(MobileSpecialRun, run_id)
        mobile_active = {MobileRunStatus.pending, MobileRunStatus.running}
        if mobile_run is None or (not force and mobile_run.status not in mobile_active):
            return False
        mobile_run.status = MobileRunStatus.failed
        mobile_run.finished_at = now
        mobile_run.summary_json = {**(mobile_run.summary_json or {}), "error_message": _LOST_WORKER_ERROR}
    else:
        from app.models.performance import PerformanceRun, PerformanceRunStatus

        performance_run = session.get(PerformanceRun, run_id)
        performance_active = {
            PerformanceRunStatus.pending.value,
            PerformanceRunStatus.running.value,
            PerformanceRunStatus.cancelling.value,
        }
        if performance_run is None or (not force and performance_run.status not in performance_active):
            return False
        performance_run.status = (
            PerformanceRunStatus.cancelled.value
            if performance_run.status == PerformanceRunStatus.cancelling.value
            else PerformanceRunStatus.failed.value
        )
        performance_run.finished_at = now
        performance_run.error_message = _LOST_WORKER_ERROR
    return True


def reconcile_expired_execution_run_leases(
    session: Session,
    *,
    now: datetime | None = None,
    limit: int = 500,
) -> dict[str, int]:
    """Expire abandoned leases and recover runs that are still non-terminal."""
    current_time = now or _utcnow()
    leases = list(
        session.scalars(
            select(ExecutionRunLease)
            .where(ExecutionRunLease.status == "active", ExecutionRunLease.expires_at <= current_time)
            .order_by(ExecutionRunLease.expires_at, ExecutionRunLease.id)
            .limit(limit)
            .with_for_update(skip_locked=True)
        )
    )
    counts = {task_type: 0 for task_type in sorted(SUPPORTED_TASK_TYPES)}
    for lease in leases:
        lease.status = "expired"
        lease.released_at = current_time
        lease.failure_reason = _LOST_WORKER_ERROR
        if _recover_run(session, lease.task_type, lease.run_id):
            counts[lease.task_type] += 1
    counts["leases"] = len(leases)
    counts["runs"] = sum(counts[task_type] for task_type in SUPPORTED_TASK_TYPES)
    return counts


class ExecutionRunLeaseGuard(AbstractContextManager["ExecutionRunLeaseGuard"]):
    """Maintain a run lease from a daemon thread while a worker body executes."""

    def __init__(self, task_type: str, run_id: int, celery_task: Any = None) -> None:
        _validate_task_type(task_type)
        self.task_type = task_type
        self.run_id = run_id
        self.lease_token = uuid.uuid4().hex
        request = getattr(celery_task, "request", None)
        task_id = getattr(request, "id", None)
        hostname = getattr(request, "hostname", None) or socket.gethostname()
        self.celery_task_id = str(task_id) if task_id else None
        self.worker_id = f"{hostname}:{task_id or self.lease_token[:12]}"
        self._stop = threading.Event()
        self._lost = threading.Event()
        self._thread: threading.Thread | None = None

    @property
    def heartbeat_interval(self) -> int:
        """Keep the configured heartbeat safely below the expiry window."""
        return min(
            settings.EXECUTION_RUN_LEASE_HEARTBEAT_SECONDS,
            max(5, settings.EXECUTION_RUN_LEASE_TTL_SECONDS // 3),
        )

    def __enter__(self) -> "ExecutionRunLeaseGuard":
        from app.core.database import sync_session_factory

        with sync_session_factory() as session:
            acquire_execution_run_lease(
                session,
                task_type=self.task_type,
                run_id=self.run_id,
                lease_token=self.lease_token,
                worker_id=self.worker_id,
                celery_task_id=self.celery_task_id,
                ttl_seconds=settings.EXECUTION_RUN_LEASE_TTL_SECONDS,
            )
        self._thread = threading.Thread(
            target=self._heartbeat_loop,
            name=f"execution-lease-{self.task_type}-{self.run_id}",
            daemon=True,
        )
        self._thread.start()
        return self

    def _heartbeat_loop(self) -> None:
        from app.core.database import sync_session_factory

        while not self._stop.wait(self.heartbeat_interval):
            try:
                with sync_session_factory() as session:
                    owned = heartbeat_execution_run_lease(
                        session,
                        task_type=self.task_type,
                        run_id=self.run_id,
                        lease_token=self.lease_token,
                        ttl_seconds=settings.EXECUTION_RUN_LEASE_TTL_SECONDS,
                    )
                if not owned:
                    self._lost.set()
                    return
            except Exception:
                logger.exception("Execution lease heartbeat failed for %s run %s", self.task_type, self.run_id)

    def __exit__(self, exc_type, exc_value, traceback) -> bool | None:
        from app.core.database import sync_session_factory

        self._stop.set()
        if self._thread is not None:
            self._thread.join(timeout=self.heartbeat_interval + 1)
        try:
            with sync_session_factory() as session:
                released = release_execution_run_lease(
                    session,
                    task_type=self.task_type,
                    run_id=self.run_id,
                    lease_token=self.lease_token,
                )
                if exc_type is not None or self._lost.is_set() or not released:
                    _recover_run(session, self.task_type, self.run_id, force=True)
                    session.commit()
        except Exception:
            logger.exception("Execution lease finalization failed for %s run %s", self.task_type, self.run_id)
        return None


def execution_run_lease(task_type: str, run_id: int, celery_task: Any = None) -> ExecutionRunLeaseGuard:
    return ExecutionRunLeaseGuard(task_type, run_id, celery_task)
