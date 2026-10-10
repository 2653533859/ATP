"""Transactional suite intents and bounded, non-replaying publication.

Only never-attempted intents are claimed. Broker exceptions and expired claims
are uncertain, not automatically retried. Local queue insertion and submission
are one SQLite transaction. Execution-side reconciliation belongs to N1.4/5.
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from threading import Event, Thread
from typing import Any, Literal
from uuid import uuid4

from cryptography.fernet import InvalidToken
from sqlalchemy import select, text, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.encryption import decrypt, encrypt
from app.models.execution_dispatch import ExecutionDispatch
from app.models.suite import SuiteRun, SuiteRunStatus, TestSuite

logger = logging.getLogger(__name__)
_stop = Event()
_wake = Event()
_thread: Thread | None = None
_CLAIM_TIMEOUT = timedelta(minutes=5)


def _mode() -> str:
    return "local" if settings.ATP_LOCAL_MODE else "server"


def _session() -> Session:
    from app.core.database import sync_session_factory

    return sync_session_factory()


def record_suite_dispatch(
    db: AsyncSession, *, run: SuiteRun, project_id: int, extra_vars: dict, queue: str
) -> ExecutionDispatch:
    """Add to the caller's transaction; never commit or publish here."""
    if not run.id or not run.identity_token or run.status != SuiteRunStatus.pending:
        raise ValueError("dispatch requires a flushed pending suite run")
    if not queue or len(queue) > 128:
        raise ValueError("invalid execution queue configuration")
    intent = ExecutionDispatch(
        project_id=project_id,
        run_id=run.id,
        run_identity=run.identity_token,
        task_name="run_test_suite",
        queue=queue,
        mode=_mode(),
        args_ciphertext=encrypt(json.dumps([run.id, extra_vars, run.trace_id], ensure_ascii=False)),
    )
    db.add(intent)
    return intent


async def get_suite_dispatch(db: AsyncSession, run: SuiteRun) -> ExecutionDispatch | None:
    return await db.scalar(
        select(ExecutionDispatch).where(
            ExecutionDispatch.task_name == "run_test_suite",
            ExecutionDispatch.run_id == run.id,
            ExecutionDispatch.run_identity == run.identity_token,
        )
    )


class _DispatchRejected(ValueError):
    def __init__(self, code: str, state: Literal["blocked", "skipped"] = "blocked") -> None:
        super().__init__(code)
        self.code = code
        self.state = state


@dataclass(frozen=True)
class _Publication:
    id: str
    claim_token: str
    task_name: str
    queue: str
    run_identity: str
    args: tuple[Any, ...] = field(repr=False)


def _prepare(db: Session, intent: ExecutionDispatch) -> tuple[Any, ...]:
    if intent.task_name != "run_test_suite":
        raise _DispatchRejected("UNSUPPORTED_TASK")
    if not intent.queue or len(intent.queue) > 128:
        raise _DispatchRejected("INVALID_QUEUE")
    run = db.get(SuiteRun, intent.run_id)
    if run is None:
        raise _DispatchRejected("RESOURCE_MISSING", "skipped")
    if not intent.run_identity or run.identity_token != intent.run_identity:
        raise _DispatchRejected("RESOURCE_CHANGED")
    suite = db.get(TestSuite, run.suite_id)
    if suite is None or suite.project_id != intent.project_id:
        raise _DispatchRejected("PROJECT_CHANGED")
    if run.status != SuiteRunStatus.pending:
        raise _DispatchRejected("RUN_NOT_PENDING", "skipped")
    try:
        args = json.loads(decrypt(intent.args_ciphertext))
    except (InvalidToken, ValueError, TypeError, UnicodeError):
        raise _DispatchRejected("PAYLOAD_INVALID") from None
    if (
        not isinstance(args, list)
        or len(args) != 3
        or type(args[0]) is not int
        or args[0] != intent.run_id
        or not isinstance(args[1], dict)
        or (args[2] is not None and not isinstance(args[2], str))
    ):
        raise _DispatchRejected("PAYLOAD_INVALID")
    return tuple(args)


def _outcome(db: Session, intent_id: str, token: str, status: str, error_code: str | None = None) -> None:
    now = datetime.now(timezone.utc)
    db.execute(
        update(ExecutionDispatch)
        .where(
            ExecutionDispatch.id == intent_id,
            ExecutionDispatch.claim_token == token,
            ExecutionDispatch.status.in_(["publishing", "uncertain"]),
        )
        .values(
            status=status,
            error_code=error_code,
            submitted_at=now if status == "submitted" else None,
            updated_at=now,
        )
        .execution_options(synchronize_session=False)
    )


def _insert_local_job(db: Session, intent: ExecutionDispatch) -> None:
    # Read the raw SQLite timestamp so local_jobs' existing identity comparison
    # and uniqueness constraint keep the exact stored representation.
    created_at = db.execute(
        text("SELECT created_at FROM suite_runs WHERE id=:id AND identity_token=:identity"),
        {"id": intent.run_id, "identity": intent.run_identity},
    ).scalar_one_or_none()
    if created_at is None:
        raise _DispatchRejected("RESOURCE_CHANGED")
    existing = db.execute(
        text("SELECT id FROM local_jobs WHERE task_name=:task AND run_id=:run " "AND run_created_at=:created"),
        {"task": intent.task_name, "run": intent.run_id, "created": created_at},
    ).first()
    if existing is not None:
        # Do not assume an older queue row belongs to the same resource.
        raise _DispatchRejected("LOCAL_JOB_CONFLICT")
    db.execute(
        text(
            "INSERT INTO local_jobs(task_name, run_id, run_created_at, args_json, dispatch_id, run_identity) "
            "VALUES (:task, :run, :created, :payload, :dispatch, :identity)"
        ),
        {
            "task": intent.task_name,
            "run": intent.run_id,
            "created": created_at,
            "payload": intent.args_ciphertext,
            "dispatch": intent.id,
            "identity": intent.run_identity,
        },
    )


def process_next_dispatch() -> bool:
    """Claim one pending intent; at most one publisher wins the compare-and-set."""
    publication: _Publication | None = None
    with _session() as db:
        intent = db.scalar(
            select(ExecutionDispatch)
            .where(ExecutionDispatch.mode == _mode(), ExecutionDispatch.status == "pending")
            .order_by(ExecutionDispatch.created_at, ExecutionDispatch.id)
            .limit(1)
        )
        if intent is None:
            return False
        token = uuid4().hex
        claimed = db.execute(
            update(ExecutionDispatch)
            .where(
                ExecutionDispatch.id == intent.id,
                ExecutionDispatch.mode == _mode(),
                ExecutionDispatch.status == "pending",
            )
            .values(
                status="publishing",
                claim_token=token,
                claimed_at=datetime.now(timezone.utc),
                attempt_count=ExecutionDispatch.attempt_count + 1,
                error_code=None,
            )
            .execution_options(synchronize_session=False)
        )
        if not getattr(claimed, "rowcount", 0):
            db.rollback()
            return False
        try:
            args = _prepare(db, intent)
            if settings.ATP_LOCAL_MODE:
                _insert_local_job(db, intent)
                _outcome(db, intent.id, token, "submitted")
            else:
                publication = _Publication(intent.id, token, intent.task_name, intent.queue, intent.run_identity, args)
        except _DispatchRejected as exc:
            _outcome(db, intent.id, token, exc.state, exc.code)
        # Local claim, queue insertion and submitted status all commit together.
        # Server claims commit BEFORE publication so an uncertain send is never
        # rolled back into pending and automatically published a second time.
        db.commit()
    if publication is None:
        return True
    try:
        from app.worker.celery_app import celery_app

        celery_app.send_task(
            publication.task_name,
            args=publication.args,
            queue=publication.queue,
            task_id=publication.id,
            # Preserve the existing 3-argument Worker contract. N1.4 can use
            # these headers for identity-aware acceptance without changing args.
            headers={"atp_dispatch_id": publication.id, "atp_run_identity": publication.run_identity},
            retry=False,
        )
    except Exception:
        with _session() as db:
            _outcome(db, publication.id, publication.claim_token, "uncertain", "BROKER_RESULT_UNKNOWN")
            db.commit()
        logger.warning("Suite dispatch %s requires broker/result verification", publication.id)
    else:
        with _session() as db:
            _outcome(db, publication.id, publication.claim_token, "submitted")
            db.commit()
    return True


def reconcile_expired_publications() -> None:
    """An expired claim may already be accepted; preserve that uncertainty."""
    with _session() as db:
        db.execute(
            update(ExecutionDispatch)
            .where(
                ExecutionDispatch.mode == _mode(),
                ExecutionDispatch.status == "publishing",
                ExecutionDispatch.claimed_at < datetime.now(timezone.utc) - _CLAIM_TIMEOUT,
            )
            .values(status="uncertain", error_code="PUBLICATION_TIMEOUT")
            .execution_options(synchronize_session=False)
        )
        db.commit()


def _loop() -> None:
    while not _stop.is_set():
        try:
            reconcile_expired_publications()
            if process_next_dispatch():
                continue
        except Exception:
            # No exception payload: database/broker errors can include secrets.
            logger.warning("Execution dispatch polling failed; verify migration and database connectivity")
            _stop.wait(5)
        _wake.wait(1)
        _wake.clear()


def wake_dispatcher() -> None:
    _wake.set()


def start_dispatcher() -> None:
    global _thread
    if _thread and _thread.is_alive():
        return
    # Fail startup if the required migration is missing instead of silently
    # returning a healthy API while all new suite runs remain undeliverable.
    with _session() as db:
        from app.models.execution_run_lease import ExecutionRunLease

        db.execute(
            select(ExecutionDispatch.id, ExecutionDispatch.execution_token, ExecutionDispatch.accepted_at).limit(0)
        )
        db.execute(select(ExecutionRunLease.run_identity).limit(0))
        from app.models.group_run_child import GroupRunChild
        from app.models.plan import PlanRun

        db.execute(select(GroupRunChild.id).limit(0))
        db.execute(select(SuiteRun.cancel_requested_at).limit(0))
        db.execute(select(PlanRun.cancel_requested_at, PlanRun.identity_token).limit(0))
    _stop.clear()
    _wake.clear()
    _thread = Thread(target=_loop, name="atp-execution-dispatch", daemon=True)
    _thread.start()


def stop_dispatcher() -> None:
    _stop.set()
    _wake.set()
    if _thread:
        _thread.join(timeout=5)
