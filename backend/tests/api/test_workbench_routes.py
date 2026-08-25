"""工作台聚合与统一任务操作的边界测试。"""

import asyncio
import types
from datetime import datetime, timedelta, timezone

import pytest
from fastapi import HTTPException

from app.api.v1 import workbench
from app.models.case import RunStatus
from app.models.mobile_special import RunStatus as MobileRunStatus
from app.models.performance import PerformanceRunStatus
from app.models.user import UserRole
from app.models.user_project import ProjectRole
from app.schemas.workbench import WorkbenchTaskRef


class _FakeResult:
    def __init__(self, rows=None):
        self.rows = list(rows or [])

    def all(self):
        return self.rows

    def scalars(self):
        return self


class _FakeDB:
    def __init__(self, results=None, objects=None):
        self.results = list(results or [])
        self.objects = dict(objects or {})
        self.rollback_count = 0

    async def execute(self, _statement):
        return self.results.pop(0) if self.results else _FakeResult()

    async def get(self, model, key):
        return self.objects.get((model.__name__, key))

    async def rollback(self):
        self.rollback_count += 1


def _now():
    return datetime(2026, 8, 24, 10, 0, tzinfo=timezone.utc)


def _task(task_type, status, *, run_id=9, created_at=None):
    return workbench._task_item(
        task_type=task_type,
        run_id=run_id,
        source_id=3,
        project_id=1,
        project_name="ATP",
        name="sample",
        status_value=status,
        created_at=created_at or _now(),
        detail_path="/runs/9",
    )


def test_task_item_exposes_domain_specific_actions():
    case = _task("case", RunStatus.failed)
    pending_case = _task("case", RunStatus.pending)
    passed_case = _task("case", RunStatus.passed)
    android = _task("android", MobileRunStatus.stopped)
    performance = _task("performance", PerformanceRunStatus.cancelled)

    assert case.can_retry is True
    assert case.can_stop is False
    assert pending_case.can_stop is False
    assert passed_case.can_retry is False
    assert android.can_retry is True
    assert performance.can_retry is True


def test_status_filters_are_restricted_to_each_domain_enum():
    failed = workbench._status_filter_for_type(workbench._FAILED_STATUSES, "case")
    assert failed == {"failed", "error"}
    assert workbench._status_filter_for_type(workbench._FAILED_STATUSES, "android") == {"failed", "stopped"}
    assert workbench._status_filter_for_type(workbench._FAILED_STATUSES, "performance") == {"failed", "cancelled"}
    assert workbench._status_filter_for_type(workbench._ACTIVE_STATUSES, "case") == {"pending", "running"}
    assert workbench._status_filter_for_type("stopped", "case") == set()


def test_collect_tasks_passes_domain_safe_status_filters(monkeypatch):
    seen = {}

    def collector(task_type):
        async def _collect(_db, _user, _project_id, status_filter, _limit):
            seen[task_type] = status_filter
            return [], False

        return _collect

    for task_type in ("case", "suite", "plan", "android", "performance"):
        monkeypatch.setattr(workbench, f"_collect_{task_type}_tasks", collector(task_type))

    asyncio.run(
        workbench._collect_tasks(_FakeDB(), types.SimpleNamespace(), None, workbench._FAILED_STATUSES, None, 10)
    )

    assert seen == {
        "case": {"failed", "error"},
        "suite": {"failed", "error"},
        "plan": {"failed", "error"},
        "android": {"failed", "stopped"},
        "performance": {"failed", "cancelled"},
    }


def test_collect_tasks_applies_offset_after_merging_domains(monkeypatch):
    seen_limits = []
    task_types = ("case", "suite", "plan", "android", "performance")

    def collector(task_type):
        async def _collect(_db, _user, _project_id, _status_filter, limit):
            seen_limits.append(limit)
            index = task_types.index(task_type)
            return [
                _task(
                    task_type,
                    "failed",
                    run_id=index * 10 + row_index,
                    created_at=_now() - timedelta(seconds=index * 3 + row_index),
                )
                for row_index in range(3)
            ], False

        return _collect

    for task_type in task_types:
        monkeypatch.setattr(workbench, f"_collect_{task_type}_tasks", collector(task_type))

    items, has_more = asyncio.run(workbench._collect_tasks(_FakeDB(), types.SimpleNamespace(), None, None, None, 2, 2))

    assert seen_limits == [4] * len(task_types)
    assert [item.run_id for item in items] == [2, 10]
    assert has_more is True


def test_retry_guard_rejects_non_retryable_status():
    ref = WorkbenchTaskRef(task_type="case", run_id=9)

    with pytest.raises(HTTPException) as exc:
        workbench._ensure_retryable(ref, RunStatus.passed)

    assert exc.value.status_code == 409


def test_retry_guard_accepts_failed_statuses_for_each_domain():
    statuses = {
        "case": RunStatus.error,
        "suite": "failed",
        "plan": "error",
        "android": MobileRunStatus.stopped,
        "performance": PerformanceRunStatus.cancelled,
    }

    for task_type, task_status in statuses.items():
        workbench._ensure_retryable(WorkbenchTaskRef(task_type=task_type, run_id=1), task_status)


def test_collect_todos_includes_review_and_reports_truncation():
    case = types.SimpleNamespace(id=3, name="登录用例", updated_at=_now(), review_status="pending")
    # One review result, five empty failed-task collectors, and one empty overdue-plan result.
    db = _FakeDB([_FakeResult([(case, "项目 A", 1)])] + [_FakeResult() for _ in range(6)])
    user = types.SimpleNamespace(id=7, role=UserRole.tester)

    todos, has_more = asyncio.run(workbench._collect_todos(db, user, 1, 10))

    assert has_more is False
    assert len(todos) == 1
    assert todos[0].kind == "case_review"
    assert todos[0].path == "/cases/3"


def test_collect_todos_applies_offset_after_priority_merge(monkeypatch):
    first_review = types.SimpleNamespace(id=3, name="登录用例", updated_at=_now(), review_status="pending")
    second_review = types.SimpleNamespace(
        id=4,
        name="支付用例",
        updated_at=_now() + timedelta(minutes=1),
        review_status="pending",
    )
    db = _FakeDB([_FakeResult([(first_review, "项目 A", 1), (second_review, "项目 A", 1)]), _FakeResult()])
    monkeypatch.setattr(
        workbench,
        "_collect_tasks",
        lambda *_args, **_kwargs: asyncio.sleep(0, result=([_task("case", "failed", run_id=10)], False)),
    )
    user = types.SimpleNamespace(id=7, role=UserRole.tester)

    todos, has_more = asyncio.run(workbench._collect_todos(db, user, 1, 1, 1))

    assert todos[0].id == "review:3"
    assert has_more is True


def test_collect_performance_tasks_uses_test_executor_metadata():
    run = types.SimpleNamespace(
        id=12,
        performance_test_id=4,
        project_id=1,
        status=PerformanceRunStatus.failed.value,
        created_at=_now(),
        started_at=None,
        finished_at=None,
        duration_ms=None,
        error_message="timeout",
    )
    db = _FakeDB([_FakeResult([(run, "压测场景", "locust", 1, "项目 A")])])
    user = types.SimpleNamespace(id=7, role=UserRole.tester)

    items, has_more = asyncio.run(workbench._collect_performance_tasks(db, user, 1, None, 10))

    assert has_more is False
    assert items[0].metadata["executor"] == "locust"


@pytest.mark.parametrize(
    ("collector_name", "row", "expected_path"),
    [
        (
            "case",
            (
                types.SimpleNamespace(
                    id=21, case_id=31, status=RunStatus.failed, created_at=_now(), duration_ms=None, error_message=None
                ),
                "登录用例",
                7,
                "项目 A",
            ),
            "/runs/21?project_id=7",
        ),
        (
            "suite",
            (
                types.SimpleNamespace(
                    id=22, suite_id=32, status="failed", created_at=_now(), duration_ms=None, error_message=None
                ),
                "回归套件",
                8,
                "项目 B",
            ),
            "/suites?project_id=8&run_id=22",
        ),
        (
            "plan",
            (
                types.SimpleNamespace(
                    id=23, plan_id=33, status="error", created_at=_now(), duration_ms=None, error_message=None
                ),
                "冒烟计划",
                9,
                "项目 C",
            ),
            "/plans?project_id=9&run_id=23",
        ),
        (
            "android",
            (
                types.SimpleNamespace(
                    id=24,
                    task_id=34,
                    status=MobileRunStatus.stopped,
                    created_at=_now(),
                    started_at=None,
                    finished_at=None,
                    duration_ms=None,
                    summary_json={},
                    task_type="monkey",
                ),
                "Karing 测试",
                10,
                "项目 D",
            ),
            "/mobile-special/reports/24?project_id=10",
        ),
        (
            "performance",
            (
                types.SimpleNamespace(
                    id=25,
                    performance_test_id=35,
                    project_id=11,
                    status=PerformanceRunStatus.failed,
                    created_at=_now(),
                    started_at=None,
                    finished_at=None,
                    duration_ms=None,
                    error_message=None,
                ),
                "接口压测",
                "k6",
                11,
                "项目 E",
            ),
            "/system/performance?project_id=11&run_id=25",
        ),
    ],
)
def test_collect_task_detail_paths_preserve_project_and_run_context(collector_name, row, expected_path):
    collector = getattr(workbench, f"_collect_{collector_name}_tasks")
    db = _FakeDB([_FakeResult([row])])
    user = types.SimpleNamespace(id=7, role=UserRole.tester)

    items, has_more = asyncio.run(collector(db, user, None, None, 10))

    assert has_more is False
    assert items[0].detail_path == expected_path


def test_retry_endpoint_does_not_dispatch_passed_run(monkeypatch):
    source = types.SimpleNamespace(status=RunStatus.passed, case_id=3)
    case = types.SimpleNamespace(module_id=8)
    module = types.SimpleNamespace(project_id=1)
    db = _FakeDB(objects={("TestRun", 9): source, ("TestCase", 3): case, ("Module", 8): module})
    user = types.SimpleNamespace(id=7, role=UserRole.tester)

    async def allow_access(*_args, **_kwargs):
        return None

    monkeypatch.setattr(workbench, "assert_project_access", allow_access)

    with pytest.raises(HTTPException) as exc:
        asyncio.run(workbench._retry_task(WorkbenchTaskRef(task_type="case", run_id=9), db, user))

    assert exc.value.status_code == 409


def test_diagnosis_endpoint_scopes_and_dispatches_non_case_task(monkeypatch):
    run = types.SimpleNamespace(project_id=1)
    db = _FakeDB(objects={("PerformanceRun", 14): run})
    user = types.SimpleNamespace(id=7, role=UserRole.tester)
    seen = {}

    async def allow_access(_db, _user, project_id, role):
        seen["access"] = (project_id, role)

    async def fake_diagnosis(_db, task_type, run_id):
        seen["dispatch"] = (task_type, run_id)
        return {
            "status": "done",
            "source": "rule",
            "summary": "压测节点异常",
            "at": "2026-08-24T10:00:00Z",
            "failed_step_count": 1,
            "screenshot_count": 0,
            "repair_suggestions": [],
            "error_samples": [],
        }

    monkeypatch.setattr(workbench, "assert_project_access", allow_access)
    monkeypatch.setattr(workbench, "generate_workbench_failure_diagnosis", fake_diagnosis)

    result = asyncio.run(workbench.diagnose_workbench_task_failure("performance", 14, db, user))

    assert seen["access"] == (1, ProjectRole.viewer)
    assert seen["dispatch"] == ("performance", 14)
    assert result["summary"] == "压测节点异常"
