"""Regression tests for unified execution-command idempotency and audit."""

import asyncio
from datetime import datetime, timedelta, timezone

import pytest
from fastapi import HTTPException
from sqlalchemy.exc import IntegrityError

from app.models import load_all_models
from app.models.audit import AuditLog
from app.models.execution_command import ExecutionCommand
from app.services.execution_commands import (
    INDETERMINATE_COMMAND_DETAIL,
    _resolve_existing,
    claim_execution_command,
    complete_execution_command,
    fail_execution_command,
    mark_execution_command_indeterminate,
    normalize_execution_command_id,
    reconcile_stale_execution_commands,
)

load_all_models()


class _FakeDB:
    def __init__(self, command=None):
        self.command = command
        self.added = []
        self.commits = 0
        self.rollbacks = 0

    def add(self, value):
        self.added.append(value)

    async def flush(self):
        return None

    async def commit(self):
        self.commits += 1

    async def rollback(self):
        self.rollbacks += 1

    async def get(self, model, key):
        if model is ExecutionCommand and self.command and self.command.id == key:
            return self.command
        return None


def _command(**overrides):
    values = {
        "id": 11,
        "user_id": 7,
        "command_id": "workbench:retry:case:9",
        "action": "retry",
        "task_type": "case",
        "run_id": 9,
        "project_id": 1,
        "source_status": "failed",
        "status": "processing",
        "response_json": {},
    }
    values.update(overrides)
    return ExecutionCommand(**values)


def test_command_id_defaults_to_stable_target_key_and_is_bounded():
    assert normalize_execution_command_id(None, action="retry", task_type="case", run_id=9) == "workbench:retry:case:9"

    with pytest.raises(HTTPException) as exc:
        normalize_execution_command_id("x" * 129, action="retry", task_type="case", run_id=9)

    assert exc.value.status_code == 422


def test_completed_command_replays_only_the_same_target():
    command = _command(status="succeeded", response_json={"status": "pending"})

    claim = _resolve_existing(command, action="retry", task_type="case", run_id=9)

    assert claim.replay_response == {"status": "pending"}
    with pytest.raises(HTTPException) as exc:
        _resolve_existing(command, action="retry", task_type="case", run_id=10)
    assert exc.value.status_code == 409


def test_processing_and_failed_commands_return_stable_errors():
    with pytest.raises(HTTPException, match="正在处理中"):
        _resolve_existing(_command(), action="retry", task_type="case", run_id=9)

    with pytest.raises(HTTPException) as exc:
        _resolve_existing(
            _command(status="failed", error_status_code=403, error_detail="权限不足"),
            action="retry",
            task_type="case",
            run_id=9,
        )
    assert exc.value.status_code == 403
    assert exc.value.detail == "权限不足"


def test_complete_command_persists_response_and_success_audit():
    command = _command()
    db = _FakeDB(command)

    asyncio.run(
        complete_execution_command(
            db,
            command,
            response={"status": "pending", "new_run_id": 12},
            username="tester",
        )
    )

    assert command.status == "succeeded"
    assert command.response_json["new_run_id"] == 12
    assert command.result_status == "pending"
    audit = next(value for value in db.added if isinstance(value, AuditLog))
    assert audit.action == "execution.retry.succeeded"
    assert "workbench:retry:case:9" in audit.detail
    assert db.commits == 1


def test_fail_command_rolls_back_action_and_persists_failure_audit():
    command = _command()
    db = _FakeDB(command)

    asyncio.run(
        fail_execution_command(
            db,
            command,
            status_code=409,
            detail="状态不允许重试",
            username="tester",
        )
    )

    assert db.rollbacks == 1
    assert db.commits == 1
    assert command.status == "failed"
    assert command.error_status_code == 409
    assert command.result_status == "failed"
    assert any(isinstance(value, AuditLog) for value in db.added)


def test_unknown_dispatch_outcome_is_indeterminate_and_audited():
    command = _command()
    db = _FakeDB(command)

    asyncio.run(mark_execution_command_indeterminate(db, command, username="tester"))

    assert db.rollbacks == 1
    assert db.commits == 1
    assert command.status == "indeterminate"
    assert command.error_status_code == 409
    assert "禁止自动重放" in command.error_detail
    audit = next(value for value in db.added if isinstance(value, AuditLog))
    assert audit.action == "execution.retry.indeterminate"
    assert "dispatch_exception" in audit.detail


class _ScalarResult:
    def __init__(self, value):
        self.value = value

    def scalar_one_or_none(self):
        return self.value


class _ConcurrentClaimDB:
    def __init__(self, existing):
        self.results = iter([None, None, existing])
        self.rollbacks = 0
        self.commits = 0

    async def execute(self, _statement):
        return _ScalarResult(next(self.results))

    def add(self, _value):
        return None

    async def commit(self):
        self.commits += 1
        if self.commits == 1:
            raise IntegrityError("insert", {}, RuntimeError("duplicate target"))

    async def rollback(self):
        self.rollbacks += 1

    async def refresh(self, _value):
        return None


def test_concurrent_claim_replays_the_global_target_winner():
    winner = _command(
        user_id=8,
        command_id="another-client-key",
        status="succeeded",
        response_json={"status": "pending", "new_run_id": 12},
    )
    db = _ConcurrentClaimDB(winner)

    claim = asyncio.run(
        claim_execution_command(
            db,
            user_id=7,
            command_id="workbench:retry:case:9",
            action="retry",
            task_type="case",
            run_id=9,
            project_id=1,
            source_status="failed",
        )
    )

    assert db.rollbacks == 1
    assert claim.command is winner
    assert claim.replay_response["new_run_id"] == 12


class _CommandListResult:
    def __init__(self, commands):
        self.commands = commands

    def scalars(self):
        return self

    def all(self):
        return self.commands


class _ReconcileSession:
    def __init__(self, commands):
        self.commands = commands
        self.added = []

    def execute(self, _statement):
        return _CommandListResult(self.commands)

    def add(self, value):
        self.added.append(value)


def test_stale_processing_claim_becomes_indeterminate_and_is_audited():
    now = datetime(2026, 9, 8, 10, 0, tzinfo=timezone.utc)
    command = _command(updated_at=now - timedelta(minutes=20))
    session = _ReconcileSession([command])

    reconciled = reconcile_stale_execution_commands(session, now=now, timeout_minutes=15)

    assert reconciled == 1
    assert command.status == "indeterminate"
    assert command.error_status_code == 409
    assert command.error_detail == INDETERMINATE_COMMAND_DETAIL
    audit = next(value for value in session.added if isinstance(value, AuditLog))
    assert audit.action == "execution.retry.indeterminate"
    assert "processing_timeout" in audit.detail


def test_indeterminate_command_never_auto_replays():
    command = _command(status="indeterminate", error_status_code=409, error_detail=INDETERMINATE_COMMAND_DETAIL)

    with pytest.raises(HTTPException) as exc:
        _resolve_existing(command, action="retry", task_type="case", run_id=9)

    assert exc.value.status_code == 409
    assert "禁止自动重放" in exc.value.detail
