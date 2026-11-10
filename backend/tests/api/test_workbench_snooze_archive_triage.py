"""Tests for workbench todo snooze, task archive, and run triage endpoints."""

from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from types import SimpleNamespace
from typing import Any

import pytest
from fastapi import HTTPException
from pydantic import ValidationError

from app.api.v1 import workbench
from app.api.v1.cases import runs
from app.models.user import UserRole
from app.models.user_project import ProjectRole
from app.schemas.case import RunTriageIn
from app.schemas.workbench import (
    WorkbenchTaskArchiveIn,
    WorkbenchTaskRef,
    WorkbenchTodoSnoozeIn,
)


class _FakeResult:
    def __init__(self, rows=None, scalar=None):
        self.rows = list(rows or [])
        self._scalar = scalar

    def all(self):
        return self.rows

    def scalars(self):
        return self

    def scalar_one_or_none(self):
        if self._scalar is not None:
            return self._scalar
        return self.rows[0] if self.rows else None

    def scalar_one(self):
        if self._scalar is not None:
            return self._scalar
        return self.rows[0] if self.rows else None


class _FakeDB:
    def __init__(self, results=None, objects=None):
        self.results = list(results or [])
        self.objects = dict(objects or {})
        self.added = []
        self.deleted = []
        self.commits = 0
        self.refreshes = 0
        self.statements = []

    async def execute(self, statement):
        self.statements.append(statement)
        return self.results.pop(0) if self.results else _FakeResult()

    async def get(self, model, key):
        return self.objects.get((getattr(model, "__name__", str(model)), key))

    def add(self, obj):
        self.added.append(obj)

    async def delete(self, obj):
        self.deleted.append(obj)

    async def commit(self):
        self.commits += 1

    async def refresh(self, _obj):
        self.refreshes += 1


def _user(user_id=7, role=UserRole.admin):
    return SimpleNamespace(id=user_id, username=f"user_{user_id}", role=role)


def test_snooze_workbench_todo_creates_snooze(monkeypatch):
    async def fake_project_access(_db, _user, _project_id, _role):
        return None

    monkeypatch.setattr(workbench, "assert_project_access", fake_project_access)

    fake_case = SimpleNamespace(id=101, module_id=201)
    fake_module = SimpleNamespace(id=201, project_id=1)
    objects = {
        ("TestCase", 101): fake_case,
        ("Module", 201): fake_module,
    }
    db = _FakeDB([_FakeResult(rows=[])], objects=objects)
    user = _user(7)
    body = WorkbenchTodoSnoozeIn(duration_hours=24, reason="等待依赖升级")

    out = asyncio.run(
        workbench.snooze_workbench_todo(
            todo_id="review:101",
            body=body,
            db=db,
            current_user=user,
        )
    )

    assert out.todo_id == "review:101"
    assert out.user_id == 7
    assert out.reason == "等待依赖升级"
    assert out.snoozed_until is not None
    assert len(db.added) == 1
    assert db.added[0].project_id == 1
    assert db.commits == 1


def test_snooze_duration_zero_rejected():
    with pytest.raises(ValidationError):
        WorkbenchTodoSnoozeIn(duration_hours=0)


def test_snooze_target_not_found_raises_404():
    db = _FakeDB([_FakeResult(rows=[])], objects={})
    user = _user(7)
    body = WorkbenchTodoSnoozeIn(duration_hours=24)

    with pytest.raises(HTTPException) as exc_info:
        asyncio.run(
            workbench.snooze_workbench_todo(
                todo_id="review:9999",
                body=body,
                db=db,
                current_user=user,
            )
        )
    assert exc_info.value.status_code == 404


def test_unsnooze_workbench_todo(monkeypatch):
    async def fake_project_access(_db, _user, _project_id, _role):
        return None

    monkeypatch.setattr(workbench, "assert_project_access", fake_project_access)

    existing_snooze = SimpleNamespace(id=1, todo_id="review:101", user_id=7, project_id=1)
    db = _FakeDB([_FakeResult(rows=[existing_snooze])])
    user = _user(7)

    res = asyncio.run(
        workbench.unsnooze_workbench_todo(
            todo_id="review:101",
            db=db,
            current_user=user,
        )
    )

    assert res["status"] == "ok"
    assert res["unsnoozed"] is True
    assert db.deleted == [existing_snooze]
    assert db.commits == 1


def test_archive_workbench_tasks(monkeypatch):
    async def fake_project_access(_db, _user, _project_id, _role):
        return None

    monkeypatch.setattr(workbench, "assert_project_access", fake_project_access)

    db = _FakeDB([_FakeResult(rows=[(14, 1)]), _FakeResult(rows=[])])
    user = _user(7, role=UserRole.engineer)
    body = WorkbenchTaskArchiveIn(tasks=[WorkbenchTaskRef(task_type="case", run_id=14)])

    out = asyncio.run(
        workbench.archive_workbench_tasks(
            body=body,
            db=db,
            current_user=user,
        )
    )

    assert out.processed == 1
    assert out.archived is True
    assert len(db.added) == 1
    assert db.added[0].project_id == 1
    assert db.commits == 1


def test_archive_task_not_found_raises_404(monkeypatch):
    async def fake_project_access(_db, _user, _project_id, _role):
        return None

    monkeypatch.setattr(workbench, "assert_project_access", fake_project_access)

    db = _FakeDB([_FakeResult(rows=[])])
    user = _user(7, role=UserRole.engineer)
    body = WorkbenchTaskArchiveIn(tasks=[WorkbenchTaskRef(task_type="case", run_id=999)])

    with pytest.raises(HTTPException) as exc_info:
        asyncio.run(
            workbench.archive_workbench_tasks(
                body=body,
                db=db,
                current_user=user,
            )
        )
    assert exc_info.value.status_code == 404


def test_unarchive_workbench_tasks(monkeypatch):
    async def fake_project_access(_db, _user, _project_id, _role):
        return None

    monkeypatch.setattr(workbench, "assert_project_access", fake_project_access)

    existing = SimpleNamespace(id=1, task_type="case", run_id=14)
    db = _FakeDB([_FakeResult(rows=[(14, 1)]), _FakeResult(rows=[existing])])
    user = _user(7, role=UserRole.engineer)
    body = WorkbenchTaskArchiveIn(tasks=[WorkbenchTaskRef(task_type="case", run_id=14)])

    out = asyncio.run(
        workbench.unarchive_workbench_tasks(
            body=body,
            db=db,
            current_user=user,
        )
    )

    assert out.processed == 1
    assert out.archived is False
    assert db.deleted == [existing]
    assert db.commits == 1


def test_snooze_failed_run_verifies_run_exists_and_sets_project(monkeypatch):
    async def fake_project_access(_db, _user, _project_id, _role):
        return None

    monkeypatch.setattr(workbench, "assert_project_access", fake_project_access)

    fake_run = SimpleNamespace(id=55, case_id=101, project_id=3)
    objects = {
        ("TestRun", 55): fake_run,
        ("TestCase", 101): SimpleNamespace(id=101, module_id=201),
        ("Module", 201): SimpleNamespace(id=201, project_id=3),
    }

    async def fake_project_id(_db, _task_type, _run_id):
        return 3

    async def fake_status(_db, _task_type, _run_id):
        return "failed"

    monkeypatch.setattr(workbench, "_workbench_task_project_id", fake_project_id)
    monkeypatch.setattr(workbench, "_workbench_task_status", fake_status)

    db = _FakeDB([_FakeResult(rows=[])], objects=objects)
    user = _user(7)
    body = WorkbenchTodoSnoozeIn(duration_hours=12, reason="环境修复中")

    out = asyncio.run(
        workbench.snooze_workbench_todo(
            todo_id="failed-run:case:55",
            body=body,
            db=db,
            current_user=user,
        )
    )

    assert out.todo_id == "failed-run:case:55"
    assert len(db.added) == 1
    assert db.added[0].project_id == 3
    assert db.commits == 1


def test_count_tasks_sql_pushdown_archived_filter():
    db = _FakeDB([_FakeResult(scalar=8)])
    user = _user(7)
    count = asyncio.run(
        workbench._count_tasks(
            db=db,
            user=user,
            project_id=1,
            status_filter="failed",
            task_type="case",
            archived_filter="exclude",
        )
    )
    assert count == 8
    assert len(db.statements) == 1


def test_count_todos_with_active_snooze_filter(monkeypatch):
    async def fake_count_tasks(*_args, **_kwargs):
        return 0

    monkeypatch.setattr(workbench, "_count_tasks", fake_count_tasks)

    # Setup active snooze for review:101
    snooze_row = SimpleNamespace(id=1, todo_id="review:101", user_id=7, project_id=1, snoozed_until=None)
    # db sequence: snooze_stmt, review_stmt, overdue_stmt
    db = _FakeDB(
        [
            _FakeResult(rows=[snooze_row]),  # snooze map
            _FakeResult(scalar=3),  # review count
            _FakeResult(scalar=1),  # overdue plans
        ]
    )
    user = _user(7, role=UserRole.admin)

    res = asyncio.run(
        workbench._count_todos(
            db=db,
            user=user,
            project_id=1,
            snooze_filter="exclude",
        )
    )

    assert res["snoozed_todos"] == 1
    assert res["pending_reviews"] == 3
    assert res["overdue_plans"] == 1


def test_update_run_triage(monkeypatch):
    run_obj = SimpleNamespace(
        id=99,
        case_id=10,
        result_summary={},
        triggered_by=7,
        status="failed",
        duration_ms=100,
        error_message="timeout",
        environment="test",
        trace_id=None,
        iteration_index=None,
        iteration_data=None,
        parent_run_id=None,
        created_at=datetime.now(timezone.utc),
        project_id=1,
        case_type="http",
        steps=[],
    )

    async def fake_get_run(_db, _user, _run_id, _role):
        return run_obj

    async def fake_audit(*_args, **_kwargs):
        return None

    monkeypatch.setattr(runs, "_get_run_with_access", fake_get_run)
    monkeypatch.setattr("app.services.audit.write_audit_log", fake_audit)

    db = _FakeDB()
    user = _user(7, role=UserRole.engineer)
    body = RunTriageIn(category="env_issue", note="第三方测试环境网关超时")

    res = asyncio.run(
        runs.update_run_triage(
            run_id=99,
            body=body,
            db=db,
            current_user=user,
        )
    )

    assert "triage" in res.result_summary
    triage = res.result_summary["triage"]
    assert triage["category"] == "env_issue"
    assert triage["note"] == "第三方测试环境网关超时"
    assert triage["triaged_by_name"] == "user_7"
    assert db.commits == 1
    assert db.refreshes == 1
