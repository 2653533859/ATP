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


def test_snooze_device_anomaly_creates_indefinite_snooze():
    fake_device = SimpleNamespace(id=42, serial="device-42", status="offline")
    objects = {
        ("Device", 42): fake_device,
    }
    db = _FakeDB([_FakeResult(rows=[])], objects=objects)
    user = _user(7, role=UserRole.engineer)
    body = WorkbenchTodoSnoozeIn(duration_hours=-1, reason="主动离线 / 忽略提醒")

    out = asyncio.run(
        workbench.snooze_workbench_todo(
            todo_id="device:42",
            body=body,
            db=db,
            current_user=user,
        )
    )

    assert out.todo_id == "device:42"
    assert out.user_id == 7
    assert out.reason == "主动离线 / 忽略提醒"
    assert out.snoozed_until is None  # -1 represents indefinite ignore
    assert len(db.added) == 1
    assert db.added[0].project_id is None
    assert db.commits == 1


def test_count_todos_with_device_anomaly_snooze_excluded(monkeypatch):
    async def fake_count_tasks(*_args, **_kwargs):
        return 0

    monkeypatch.setattr(workbench, "_count_tasks", fake_count_tasks)

    snooze_row = SimpleNamespace(id=1, todo_id="device:42", user_id=7, project_id=None, snoozed_until=None)
    # db sequence when project_id is None: snooze_stmt, review_stmt, overdue_stmt, device_stmt
    db = _FakeDB(
        [
            _FakeResult(rows=[snooze_row]),  # snooze map
            _FakeResult(scalar=0),  # review count
            _FakeResult(scalar=0),  # overdue plans
            _FakeResult(scalar=0),  # device anomalies (excluded device:42)
        ]
    )
    user = _user(7, role=UserRole.admin)

    res = asyncio.run(
        workbench._count_todos(
            db=db,
            user=user,
            project_id=None,
            snooze_filter="exclude",
        )
    )

    assert res["snoozed_todos"] == 1
    assert res["device_anomalies"] == 0
    # Check that device_stmt added not_in constraint
    device_stmt_str = str(db.statements[-1])
    assert "devices.id NOT IN" in device_stmt_str


def test_workbench_overview_snooze_count_excludes_stale_and_deletes_todos(tmp_path, monkeypatch):
    from fastapi import FastAPI
    from httpx import ASGITransport, AsyncClient
    from sqlalchemy import select
    from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

    from app.api.deps import get_current_user
    from app.core.database import get_db
    from app.models.base import Base
    from app.models.bootstrap import load_all_models
    from app.models.case import CaseStatus, CaseType, RunStatus, TestCase, TestRun
    from app.models.project import Module, Project
    from app.models.workbench import WorkbenchArchivedTask, WorkbenchTodoSnooze

    load_all_models()

    async def _run():
        engine = create_async_engine(f"sqlite+aiosqlite:///{tmp_path / 'wb.sqlite3'}")
        sessions = async_sessionmaker(engine, expire_on_commit=False)
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)

        try:
            async with sessions() as db:
                from app.models.user import User

                admin = User(username="wb_admin", email="wb@t.local", hashed_password="x", role=UserRole.admin)
                db.add(admin)
                await db.flush()
                proj = Project(name="WB", owner_id=admin.id)
                db.add(proj)
                await db.flush()
                mod = Module(name="M1", project_id=proj.id)
                db.add(mod)
                await db.flush()

                pending_snoozed_case = TestCase(
                    module_id=mod.id,
                    name="SnoozedReview",
                    case_code="TC-WB-1",
                    summary="s",
                    case_type=CaseType.api,
                    status=CaseStatus.draft,
                    review_status="pending",
                    creator_id=admin.id,
                )
                approved_stale_case = TestCase(
                    module_id=mod.id,
                    name="ApprovedStale",
                    case_code="TC-WB-2",
                    summary="s",
                    case_type=CaseType.api,
                    status=CaseStatus.active,
                    review_status="approved",
                    creator_id=admin.id,
                )
                active_case = TestCase(
                    module_id=mod.id,
                    name="ActiveReview",
                    case_code="TC-WB-3",
                    summary="s",
                    case_type=CaseType.api,
                    status=CaseStatus.draft,
                    review_status="pending",
                    creator_id=admin.id,
                )
                db.add_all([pending_snoozed_case, approved_stale_case, active_case])
                await db.flush()

                failed_snoozed_run = TestRun(
                    case_id=approved_stale_case.id,
                    triggered_by=admin.id,
                    status=RunStatus.failed,
                )
                db.add(failed_snoozed_run)
                await db.flush()

                db.add_all(
                    [
                        WorkbenchTodoSnooze(
                            todo_id=f"review:{pending_snoozed_case.id}",
                            user_id=admin.id,
                            project_id=proj.id,
                            reason="已忽略",
                        ),
                        WorkbenchTodoSnooze(
                            todo_id=f"failed-run:case:{failed_snoozed_run.id}",
                            user_id=admin.id,
                            project_id=proj.id,
                            reason="已忽略",
                        ),
                        # 2 stale snooze rows (one approved case, one nonexistent run)
                        WorkbenchTodoSnooze(
                            todo_id=f"review:{approved_stale_case.id}",
                            user_id=admin.id,
                            project_id=proj.id,
                            reason="stale-approved",
                        ),
                        WorkbenchTodoSnooze(
                            todo_id="failed-run:case:999999",
                            user_id=admin.id,
                            project_id=proj.id,
                            reason="stale-missing",
                        ),
                    ]
                )
                await db.commit()
                pending_cid = pending_snoozed_case.id
                approved_cid = approved_stale_case.id
                failed_rid = failed_snoozed_run.id
                actor = admin

            app = FastAPI()
            app.include_router(workbench.router, prefix="/api/v1")

            async def _override_db():
                async with sessions() as session:
                    yield session

            app.dependency_overrides[get_db] = _override_db
            app.dependency_overrides[get_current_user] = lambda: actor
            for r in workbench.router.routes:
                dependant = getattr(r, "dependant", None)
                if dependant is None:
                    continue
                for dep in getattr(dependant, "dependencies", []) or []:
                    if dep.call is not None:
                        if dep.name == "db":
                            app.dependency_overrides[dep.call] = _override_db
                        elif dep.name in {"current_user", "user", "_user"}:
                            app.dependency_overrides[dep.call] = lambda: actor

            monkeypatch.setattr("app.core.config.settings.ATP_LOCAL_MODE", False)

            async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
                only_res = await client.get("/api/v1/workbench/overview", params={"snooze_filter": "only"})
                assert only_res.status_code == 200
                only_data = only_res.json()
                assert len(only_data["todos"]) == 2
                assert only_data["counts"]["snoozed_todos"] == 2
                assert only_data["counts"]["total_todos"] == 2
                assert only_data["counts"]["active_todos"] == 1

                excl_res = await client.get("/api/v1/workbench/overview", params={"snooze_filter": "exclude"})
                assert excl_res.status_code == 200
                excl_data = excl_res.json()
                assert len(excl_data["todos"]) == 1
                assert excl_data["counts"]["active_todos"] == 1
                assert excl_data["counts"]["snoozed_todos"] == 2

                # Deleting an approved case todo is rejected (409)
                bad_rev = await client.delete(f"/api/v1/workbench/todos/review:{approved_cid}")
                assert bad_rev.status_code == 409

                # Deleting the snoozed failed run removes run + snooze
                del_run = await client.delete(f"/api/v1/workbench/todos/failed-run:case:{failed_rid}")
                assert del_run.status_code == 200
                assert del_run.json()["deleted"] is True

                # Deleting the orphaned stale snooze removes it cleanly
                del_orphan = await client.delete("/api/v1/workbench/todos/failed-run:case:999999")
                assert del_orphan.status_code == 200

                # Deleting the pending-review case removes case + snooze
                del_rev = await client.delete(f"/api/v1/workbench/todos/review:{pending_cid}")
                assert del_rev.status_code == 200

                after_only = await client.get("/api/v1/workbench/overview", params={"snooze_filter": "only"})
                assert after_only.status_code == 200
                assert after_only.json()["todos"] == []
                assert after_only.json()["counts"]["snoozed_todos"] == 0

            async with sessions() as db:
                assert await db.get(TestRun, failed_rid) is None
                assert await db.get(TestCase, pending_cid) is None
                remaining = (await db.scalars(select(WorkbenchTodoSnooze.todo_id))).all()
                assert remaining == [f"review:{approved_cid}"]
                assert (await db.scalars(select(WorkbenchArchivedTask))).all() == []
        finally:
            await engine.dispose()

    asyncio.run(_run())
