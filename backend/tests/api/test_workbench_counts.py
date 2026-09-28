"""Workbench overview counts and pagination use the same scoped sources."""

import asyncio
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

import pytest
from fastapi import HTTPException

from app.api.v1 import workbench
from app.models.user import UserRole


class _CountResult:
    def __init__(self, count):
        self.count = count

    def scalar_one(self):
        return self.count

    def all(self):
        return self.count

    def scalars(self):
        return self


class _CountDB:
    def __init__(self, counts):
        self.counts = list(counts)
        self.statements = []

    async def execute(self, statement):
        self.statements.append(statement)
        return _CountResult(self.counts.pop(0))


def _user(role=UserRole.admin):
    return SimpleNamespace(id=7, role=role)


def test_count_tasks_includes_each_domain_and_can_select_one():
    db = _CountDB([1, 2, 3, 4, 5])

    all_count = asyncio.run(workbench._count_tasks(db, _user(), None, None, None))
    one_count = asyncio.run(workbench._count_tasks(_CountDB([7]), _user(), 1, "failed", "case"))

    assert all_count == 15
    assert one_count == 7
    assert len(db.statements) == 5


def test_count_todos_adds_failed_runs_and_device_anomalies(monkeypatch):
    calls = []

    async def count_tasks(_db, _user, _project_id, status_filter, _task_type):
        calls.append(status_filter)
        return 3 if status_filter == workbench._FAILED_STATUSES else 4

    monkeypatch.setattr(workbench, "_count_tasks", count_tasks)
    db = _CountDB([2, 1, 5])

    counts = asyncio.run(workbench._count_todos(db, _user(), None))

    assert counts == {
        "pending_reviews": 2,
        "failed_runs": 3,
        "overdue_plans": 1,
        "device_anomalies": 5,
        "active_tasks": 4,
        "total_todos": 11,
    }
    assert calls == [workbench._FAILED_STATUSES, workbench._ACTIVE_STATUSES]


def test_workbench_overview_and_task_page_preserve_access_and_counts(monkeypatch):
    seen_roles = []

    async def access(_db, _user, _project_id, role):
        seen_roles.append(role)

    async def collect_todos(*_args):
        return [], True

    async def collect_tasks(*_args):
        return [], False

    async def count_todos(*_args):
        return {
            "pending_reviews": 0,
            "failed_runs": 0,
            "overdue_plans": 0,
            "device_anomalies": 0,
            "active_tasks": 0,
            "total_todos": 0,
        }

    async def count_tasks(*_args):
        return 7

    monkeypatch.setattr(workbench, "assert_project_access", access)
    monkeypatch.setattr(workbench, "_collect_todos", collect_todos)
    monkeypatch.setattr(workbench, "_collect_tasks", collect_tasks)
    monkeypatch.setattr(workbench, "_count_todos", count_todos)
    monkeypatch.setattr(workbench, "_count_tasks", count_tasks)

    overview = asyncio.run(
        workbench.get_workbench_overview(
            project_id=1, todo_limit=10, todo_offset=0, task_limit=10, db=object(), current_user=_user()
        )
    )
    page = asyncio.run(
        workbench.list_workbench_tasks(
            project_id=1,
            status_filter="failed",
            task_type="case",
            limit=10,
            offset=0,
            db=object(),
            current_user=_user(),
        )
    )

    assert overview.has_more_todos is True
    assert overview.counts["returned_tasks"] == 0
    assert page.total == 7 and page.items == []
    assert seen_roles == [workbench.ProjectRole.viewer, workbench.ProjectRole.viewer]

    with pytest.raises(HTTPException) as invalid:
        asyncio.run(
            workbench.list_workbench_tasks(
                project_id=None,
                status_filter=None,
                task_type="unknown",
                limit=10,
                offset=0,
                db=object(),
                current_user=_user(),
            )
        )
    assert invalid.value.status_code == 400


def test_collect_todos_merges_review_failure_overdue_and_device_sources(monkeypatch):
    now = datetime.now(timezone.utc)
    case = SimpleNamespace(id=11, name="登录", review_status="pending", updated_at=now)
    plan = SimpleNamespace(id=12, project_id=1, name="夜间回归", updated_at=now, next_run_at=now - timedelta(hours=1))
    device = SimpleNamespace(id=13, name="Pixel", serial="device-13", status="offline", last_seen_at=now)
    db = _CountDB([[(case, "ATP", 1)], [(plan, "ATP")], [device]])
    failed = workbench._task_item(
        task_type="case",
        run_id=14,
        source_id=11,
        project_id=1,
        project_name="ATP",
        name="登录运行",
        status_value="failed",
        created_at=now,
        detail_path="/runs/14",
        error_message="请求失败",
    )

    async def collect_tasks(*_args):
        return [failed], False

    monkeypatch.setattr(workbench, "_collect_tasks", collect_tasks)

    items, has_more = asyncio.run(workbench._collect_todos(db, _user(), None, limit=10))

    assert {item.kind for item in items} == {"case_review", "failed_run", "overdue_plan", "device_anomaly"}
    assert items[0].kind in {"failed_run", "overdue_plan"}
    assert has_more is False
