"""Accept a suite message once, before entering the existing execution lease.

Acceptance is permanent: a crash after accepting is a reconciliation case,
never permission to execute the same intent again.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

from sqlalchemy import select, update

from app.core.config import settings
from app.models.execution_dispatch import ExecutionDispatch
from app.models.suite import SuiteRun, SuiteRunStatus, TestSuite
from app.services.execution_dispatch import _DispatchRejected, _prepare


# 执行端拒绝投递时返回的固定结果；本地队列据此把队列行标记为 skipped。
# 生产方与消费方共用同一常量，避免跨层比较字面量字典。
SUITE_DELIVERY_SKIPPED: dict[str, str] = {"suite_delivery": "skipped"}


class SuiteDeliveryRejected(RuntimeError):
    """A delivery cannot safely start; its run is left untouched."""


def accept_suite_delivery(task: Any, run_id: int, extra_vars: dict, trace_id: str | None) -> str:
    """Return the current UUID only after an atomic, durable acceptance."""
    from app.core.database import sync_session_factory

    request = getattr(task, "request", None)
    headers = getattr(request, "headers", None) or {}
    if not isinstance(headers, dict):
        raise SuiteDeliveryRejected("INVALID_HEADERS")
    dispatch_id = headers.get("atp_dispatch_id")
    identity = headers.get("atp_run_identity")
    with sync_session_factory() as db:
        run = db.get(SuiteRun, run_id)
        if run is None or run.status != SuiteRunStatus.pending:
            raise SuiteDeliveryRejected("RUN_NOT_PENDING")
        if dispatch_id is None and identity is None:
            existing_intent_id = db.scalar(
                select(ExecutionDispatch.id).where(
                    ExecutionDispatch.task_name == "run_test_suite",
                    ExecutionDispatch.run_identity == run.identity_token,
                )
            )
            if existing_intent_id is not None:
                raise SuiteDeliveryRejected("DISPATCH_HEADERS_REQUIRED")
            # Existing plan/legacy messages retain their lease contract. Their
            # current UUID is still checked again before changing run state.
            return run.identity_token
        if (
            not isinstance(dispatch_id, str)
            or not isinstance(identity, str)
            or identity != run.identity_token
            or getattr(request, "id", None) != dispatch_id
        ):
            raise SuiteDeliveryRejected("DELIVERY_IDENTITY_MISMATCH")
        intent = db.get(ExecutionDispatch, dispatch_id)
        mode = "local" if settings.ATP_LOCAL_MODE else "server"
        if (
            intent is None
            or intent.mode != mode
            or intent.run_id != run_id
            or intent.run_identity != identity
            or intent.execution_token is not None
            or intent.status not in {"publishing", "submitted", "uncertain"}
        ):
            raise SuiteDeliveryRejected("INTENT_NOT_ACCEPTABLE")
        try:
            expected = _prepare(db, intent)
        except _DispatchRejected as exc:
            raise SuiteDeliveryRejected(exc.code) from None
        if json.dumps(expected, sort_keys=True) != json.dumps([run_id, extra_vars, trace_id], sort_keys=True):
            raise SuiteDeliveryRejected("DELIVERY_PAYLOAD_MISMATCH")
        current_run = (
            select(SuiteRun.id)
            .join(TestSuite, TestSuite.id == SuiteRun.suite_id)
            .where(
                SuiteRun.id == run_id,
                SuiteRun.identity_token == identity,
                SuiteRun.status == SuiteRunStatus.pending,
                TestSuite.project_id == intent.project_id,
            )
            .exists()
        )
        now = datetime.now(timezone.utc)
        result = db.execute(
            update(ExecutionDispatch)
            .where(
                ExecutionDispatch.id == dispatch_id,
                ExecutionDispatch.execution_token.is_(None),
                ExecutionDispatch.status.in_(["publishing", "submitted", "uncertain"]),
                current_run,
            )
            .values(
                execution_token=uuid4().hex,
                accepted_at=now,
                status="submitted",
                submitted_at=now,
                error_code=None,
            )
            .execution_options(synchronize_session=False)
        )
        if getattr(result, "rowcount", 0) != 1:
            db.rollback()
            raise SuiteDeliveryRejected("DELIVERY_ALREADY_ACCEPTED")
        db.commit()
        return identity
