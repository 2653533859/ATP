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
        self.statements = []

    async def execute(self, statement):
        self.statements.append(statement)
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

    user = types.SimpleNamespace(id=1, role=UserRole.admin)
    items, has_more = asyncio.run(workbench._collect_tasks(_FakeDB(), user, None, None, None, 2, 2))

    assert seen_limits == [4] * len(task_types)
    assert [item.run_id for item in items] == [2, 10]
    assert has_more is True


def test_task_actions_are_hidden_for_project_viewers():
    task = _task("case", "failed")
    db = _FakeDB([_FakeResult([])])
    user = types.SimpleNamespace(id=7, role=UserRole.viewer)

    asyncio.run(workbench._apply_task_action_permissions(db, user, [task]))

    assert task.can_retry is False
    assert task.can_stop is False


def test_project_editor_can_retry_regular_tasks_but_needs_engineer_role_for_special_tasks():
    case = _task("case", "failed")
    android = _task("android", "stopped")
    performance = _task("performance", "failed")
    db = _FakeDB([_FakeResult([1])])
    user = types.SimpleNamespace(id=7, role=UserRole.tester)

    asyncio.run(workbench._apply_task_action_permissions(db, user, [case, android, performance]))

    assert case.can_retry is True
    assert android.can_retry is False
    assert performance.can_retry is False


def test_engineer_project_editor_can_operate_special_tasks():
    android = _task("android", "stopped")
    performance = _task("performance", "running")
    db = _FakeDB([_FakeResult([1])])
    user = types.SimpleNamespace(id=8, role=UserRole.engineer)

    asyncio.run(workbench._apply_task_action_permissions(db, user, [android, performance]))

    assert android.can_retry is True
    assert performance.can_stop is True


def test_archived_project_hides_actions_even_from_admin():
    task = _task("suite", "failed")
    db = _FakeDB([_FakeResult([])])
    user = types.SimpleNamespace(id=1, role=UserRole.admin)

    asyncio.run(workbench._apply_task_action_permissions(db, user, [task]))

    assert task.can_retry is False


def test_task_permission_mask_skips_query_when_page_has_no_actions():
    task = _task("case", "passed")
    db = _FakeDB()
    user = types.SimpleNamespace(id=1, role=UserRole.admin)

    asyncio.run(workbench._apply_task_action_permissions(db, user, [task]))

    assert db.statements == []


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


def test_idempotent_action_replays_completed_response_without_dispatch(monkeypatch):
    db = _FakeDB()
    user = types.SimpleNamespace(id=7, username="tester", role=UserRole.tester)
    seen = {"dispatch": 0}

    async def project_id(*_args):
        return 1

    async def task_status(*_args):
        return "failed"

    async def claim(*_args, **_kwargs):
        return types.SimpleNamespace(
            command=types.SimpleNamespace(),
            replay_response={
                "action": "retry",
                "task_type": "case",
                "run_id": 9,
                "new_run_id": 10,
                "status": "pending",
                "message": "已创建新的执行任务",
                "command_id": "workbench:retry:case:9",
                "replayed": False,
            },
        )

    async def dispatch(*_args):
        seen["dispatch"] += 1

    monkeypatch.setattr(workbench, "_workbench_task_project_id", project_id)
    monkeypatch.setattr(workbench, "_workbench_task_status", task_status)
    monkeypatch.setattr(workbench, "claim_execution_command", claim)
    monkeypatch.setattr(workbench, "_execute_action", dispatch)

    result = asyncio.run(
        workbench._execute_idempotent_action(
            "retry",
            WorkbenchTaskRef(task_type="case", run_id=9),
            db,
            user,
        )
    )

    assert result.new_run_id == 10
    assert result.replayed is True
    assert seen["dispatch"] == 0


def test_idempotent_action_completes_claim_after_dispatch(monkeypatch):
    db = _FakeDB()
    user = types.SimpleNamespace(id=7, username="tester", role=UserRole.tester)
    command = types.SimpleNamespace()
    completed = {}

    async def project_id(*_args):
        return 1

    async def task_status(*_args):
        return "failed"

    async def claim(*_args, **_kwargs):
        return types.SimpleNamespace(command=command, replay_response=None)

    async def dispatch(*_args):
        return workbench.WorkbenchTaskActionOut(
            action="retry",
            task_type="case",
            run_id=9,
            new_run_id=10,
            status="pending",
            message="已创建新的执行任务",
        )

    async def complete(_db, claimed, **kwargs):
        completed["command"] = claimed
        completed.update(kwargs)

    monkeypatch.setattr(workbench, "_workbench_task_project_id", project_id)
    monkeypatch.setattr(workbench, "_workbench_task_status", task_status)
    monkeypatch.setattr(workbench, "claim_execution_command", claim)
    monkeypatch.setattr(workbench, "_execute_action", dispatch)
    monkeypatch.setattr(workbench, "complete_execution_command", complete)

    result = asyncio.run(
        workbench._execute_idempotent_action(
            "retry",
            WorkbenchTaskRef(task_type="case", run_id=9),
            db,
            user,
        )
    )

    assert result.command_id == "workbench:retry:case:9"
    assert completed["command"] is command
    assert completed["response"]["new_run_id"] == 10


def test_idempotent_action_checks_access_before_replaying(monkeypatch):
    db = _FakeDB()
    user = types.SimpleNamespace(id=7, username="viewer", role=UserRole.viewer)

    async def project_id(*_args):
        return 1

    async def deny_access(*_args, **_kwargs):
        raise HTTPException(status_code=403, detail="项目权限不足")

    async def must_not_claim(*_args, **_kwargs):
        pytest.fail("无权限请求不得读取或重放既有命令")

    monkeypatch.setattr(workbench, "_workbench_task_project_id", project_id)
    monkeypatch.setattr(workbench, "assert_project_access", deny_access)
    monkeypatch.setattr(workbench, "claim_execution_command", must_not_claim)

    with pytest.raises(HTTPException) as exc:
        asyncio.run(
            workbench._execute_idempotent_action(
                "retry",
                WorkbenchTaskRef(task_type="case", run_id=9),
                db,
                user,
            )
        )

    assert exc.value.status_code == 403


def test_unexpected_dispatch_failure_is_marked_indeterminate(monkeypatch):
    db = _FakeDB()
    user = types.SimpleNamespace(id=7, username="tester", role=UserRole.tester)
    command = types.SimpleNamespace()
    marked = {}

    async def project_id(*_args):
        return 1

    async def task_status(*_args):
        return "failed"

    async def allow_access(*_args, **_kwargs):
        return None

    async def claim(*_args, **_kwargs):
        return types.SimpleNamespace(command=command, replay_response=None)

    async def dispatch(*_args):
        raise RuntimeError("connection dropped after dispatch")

    async def mark(_db, claimed, **kwargs):
        marked["command"] = claimed
        marked.update(kwargs)

    monkeypatch.setattr(workbench, "_workbench_task_project_id", project_id)
    monkeypatch.setattr(workbench, "_workbench_task_status", task_status)
    monkeypatch.setattr(workbench, "assert_project_access", allow_access)
    monkeypatch.setattr(workbench, "claim_execution_command", claim)
    monkeypatch.setattr(workbench, "_execute_action", dispatch)
    monkeypatch.setattr(workbench, "mark_execution_command_indeterminate", mark)

    with pytest.raises(RuntimeError, match="connection dropped"):
        asyncio.run(
            workbench._execute_idempotent_action(
                "retry",
                WorkbenchTaskRef(task_type="case", run_id=9),
                db,
                user,
            )
        )

    assert marked["command"] is command
    assert marked["username"] == "tester"


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
