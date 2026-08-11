"""run_test_case / run_test_suite / run_test_plan / check_* 任务主体的单元缝测试。

约定（Q13-01 执行链覆盖的通用手法）：
- 导入 tasks 前 stub celery/redis/tracing 等基础设施；async_runner.run_async 换成
  真正执行 asyncio.run，使 Celery task 函数体可以在测试内同步驱动。
- AsyncSessionLocal 通过 conftest 的 app.core.database stub 替换为返回 FakeDB 的工厂。
- 函数体内延迟导入的协作模块（notifier/exports/dashboard_alerts）用 sys.modules 注入。
- 领域对象用 SimpleNamespace 鸭子类型；FakeDB 以 (模型名, 主键) 定位对象。
"""

import asyncio
import importlib
import sys
import types
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

_REAL_BOOTSTRAP = importlib.import_module("app.models.bootstrap")
_REAL_TRACING = importlib.import_module("app.core.tracing")
_REAL_DISPATCH = importlib.import_module("app.worker.case_dispatch")
_REAL_ENCRYPTION = importlib.import_module("app.core.encryption")


class _FakeCeleryApp:
    def task(self, *args, **kwargs):
        def decorator(func):
            func.delay = lambda *a, **kw: None
            return func

        return decorator


sys.modules["app.worker.celery_app"] = types.SimpleNamespace(celery_app=_FakeCeleryApp())
sys.modules["app.worker.case_dispatch"] = types.SimpleNamespace(dispatch_case=None)
sys.modules["app.models.bootstrap"] = types.SimpleNamespace(load_all_models=lambda: None)
sys.modules["app.core.redis_client"] = types.SimpleNamespace(
    publish_run_event=None,
    delete_json_cache_pattern=None,
    get_json_cache=lambda *args, **kwargs: None,
    set_json_cache=lambda *args, **kwargs: None,
    delete_json_cache=lambda *args, **kwargs: None,
)
sys.modules["app.core.encryption"] = types.SimpleNamespace(decrypt_env_vars=lambda values: {"k": "v"})
sys.modules["app.core.tracing"] = types.SimpleNamespace(
    get_trace_id=lambda: None,
    generate_trace_id=lambda: "trace-chain",
    set_trace_id=lambda value: value,
    reset_trace_id=lambda _token: None,
    attach_app_trace_id_to_current_span=lambda *args, **kwargs: None,
)
sys.modules["app.worker.async_runner"] = types.SimpleNamespace(run_async=lambda coro: asyncio.run(coro))
# 若其它测试已把真实 app.worker.tasks 导入（捕获真实 run_async），仅 pop sys.modules 不够——
# app.worker 包对象仍缓存 tasks 属性，`from app.worker import tasks` 会拿到旧模块。
# 用 importlib.import_module 强制按上面注入的 stub 重新求值。
sys.modules.pop("app.worker.tasks", None)
tasks = importlib.import_module("app.worker.tasks")  # noqa: E402

sys.modules["app.models.bootstrap"] = _REAL_BOOTSTRAP
sys.modules["app.core.tracing"] = _REAL_TRACING
sys.modules["app.worker.case_dispatch"] = _REAL_DISPATCH
sys.modules["app.core.encryption"] = _REAL_ENCRYPTION

# _create_case_run/_execute_plan_suite 会实例化真实 ORM 模型（TestRun/SuiteRun/PlanRun），
# 需要完整的 mapper 注册（Project 等关系模型），因此恢复后真正加载一次。
_REAL_BOOTSTRAP.load_all_models()


class _Obj(types.SimpleNamespace):
    """允许缺省属性读取为 None 的领域对象替身。"""

    def __getattr__(self, name):
        return None


class _FakeResult:
    def __init__(self, rows):
        self._rows = rows

    def scalars(self):
        return self

    def all(self):
        return self._rows

    def first(self):
        return self._rows[0] if self._rows else None


class _FakeDB:
    def __init__(self, objects=None, execute_rows=None):
        # objects: {(模型类名, 主键): 对象}
        self.objects = dict(objects or {})
        self.added = []
        self.commits = 0
        self.execute_rows = list(execute_rows or [])
        self._next_id = 9000

    async def get(self, model, pk):
        return self.objects.get((model.__name__, pk))

    def add(self, obj):
        if not getattr(obj, "id", None):
            obj.id = self._next_id
            self._next_id += 1
        self.added.append(obj)

    async def commit(self):
        self.commits += 1

    async def refresh(self, obj):
        return None

    async def execute(self, _query):
        rows = self.execute_rows.pop(0) if self.execute_rows else []
        return _FakeResult(rows)

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        return False


def _install_session(monkeypatch, db):
    monkeypatch.setattr(sys.modules["app.core.database"], "AsyncSessionLocal", lambda: db, raising=False)


def _install_notifier(monkeypatch, *, html_enabled=False, fail=False, calls=None):
    async def email_html_report_enabled(_db, _project_id):
        return html_enabled

    async def send_notifications(_db, project_id, payload, report_html=None):
        if fail:
            raise RuntimeError("notify down")
        if calls is not None:
            calls.append({"project_id": project_id, "payload": payload, "report_html": report_html})

    monkeypatch.setitem(
        sys.modules,
        "app.services.notifier",
        types.SimpleNamespace(
            email_html_report_enabled=email_html_report_enabled,
            send_notifications=send_notifications,
        ),
    )


def _install_exports(monkeypatch, html="<html>report</html>"):
    async def _build_suite_run_report_html(_db, _run):
        return html

    async def _build_plan_run_report_html(_db, _run):
        return html

    monkeypatch.setitem(
        sys.modules,
        "app.api.v1.exports",
        types.SimpleNamespace(
            _build_suite_run_report_html=_build_suite_run_report_html,
            _build_plan_run_report_html=_build_plan_run_report_html,
            _extract_minio_object=lambda url: None,
        ),
    )


def _publish_recorder(monkeypatch):
    events = []

    async def publish(run_id, payload):
        events.append({"run_id": run_id, **payload})

    monkeypatch.setattr(tasks, "publish_run_event", publish)
    return events


# ── 基础帮助函数 ────────────────────────────────────────────


def test_safe_publish_run_event_swallows_publish_failures(monkeypatch):
    async def broken_publish(_run_id, _payload):
        raise RuntimeError("redis down")

    monkeypatch.setattr(tasks, "publish_run_event", broken_publish)
    asyncio.run(tasks._safe_publish_run_event(1, {"type": "run_status"}))


def test_safe_invalidate_stats_cache_swallows_failures(monkeypatch):
    async def broken_delete(_pattern):
        raise RuntimeError("redis down")

    monkeypatch.setattr(tasks, "delete_json_cache_pattern", broken_delete)
    asyncio.run(tasks._safe_invalidate_stats_cache())


def test_record_run_outcome_ignores_unknown_status_and_metric_errors(monkeypatch):
    tasks._record_run_outcome("case", "pending")  # 非终态直接忽略

    class _BrokenMetric:
        def labels(self, **_kw):
            raise RuntimeError("registry gone")

    monkeypatch.setitem(sys.modules, "app.core.metrics", types.SimpleNamespace(RUN_OUTCOMES=_BrokenMetric()))
    tasks._record_run_outcome("case", types.SimpleNamespace(value="passed"))


def test_suite_run_should_stop_returns_false_without_cases():
    assert (
        tasks._suite_run_should_stop({"total": 0, "passed": 0, "failed": 0, "error": 0}, 0, "fast-fail", 0.8) is False
    )


# ── _create_case_run / _execute_case_run ───────────────────


def _suite_run_stub():
    return _Obj(id=500, triggered_by=7, trace_id="trace-suite", environment="staging")


def test_execute_case_run_records_dispatch_success(monkeypatch):
    dispatched = []

    async def fake_dispatch(_db, case_run, _case, _extra):
        case_run.status = types.SimpleNamespace(value="passed")
        dispatched.append(case_run)

    monkeypatch.setattr(tasks, "dispatch_case", fake_dispatch)
    db = _FakeDB()
    case = _Obj(id=11, name="Case-11")

    result = asyncio.run(tasks._execute_case_run(db, _suite_run_stub(), case, {}))

    assert dispatched and result == {
        "case_id": 11,
        "case_name": "Case-11",
        "run_id": dispatched[0].id,
        "status": "passed",
    }
    created = db.added[0]
    assert created.triggered_by == 7 and created.trace_id == "trace-suite" and created.environment == "staging"


def test_execute_case_run_marks_error_when_dispatch_raises(monkeypatch):
    async def broken_dispatch(_db, _case_run, _case, _extra):
        raise RuntimeError("executor exploded")

    monkeypatch.setattr(tasks, "dispatch_case", broken_dispatch)
    db = _FakeDB()

    result = asyncio.run(tasks._execute_case_run(db, _suite_run_stub(), _Obj(id=12, name="Case-12"), {}))

    assert result["status"] == "error"
    assert db.added[0].error_message == "executor exploded"


def test_mark_flaky_case_results_flags_unstable_cases():
    from app.models.case import RunStatus

    rows = [
        types.SimpleNamespace(case_id=1, status=RunStatus.passed),
        types.SimpleNamespace(case_id=1, status=RunStatus.failed),
        types.SimpleNamespace(case_id=1, status=RunStatus.passed),
        types.SimpleNamespace(case_id=1, status=RunStatus.failed),
        types.SimpleNamespace(case_id=2, status=RunStatus.passed),
    ]
    db = _FakeDB(execute_rows=[rows])
    results = [
        {"case_id": 1, "status": "failed"},
        {"case_id": 2, "status": "passed"},
        {"case_id": None, "status": "error"},
    ]

    asyncio.run(tasks._mark_flaky_case_results(db, results))

    assert results[0]["flaky"] is True and results[0]["flaky_failure_rate"] == 50.0
    assert results[1]["flaky"] is False  # 样本量不足 4


def test_mark_flaky_case_results_returns_early_without_case_ids():
    db = _FakeDB()
    asyncio.run(tasks._mark_flaky_case_results(db, [{"case_id": None}]))
    assert db.execute_rows == []


# ── run_test_case ───────────────────────────────────────────


def test_run_test_case_returns_when_run_missing(monkeypatch):
    db = _FakeDB()
    _install_session(monkeypatch, db)

    tasks.run_test_case(None, 404, {})

    assert db.commits == 0


def test_run_test_case_happy_path_publishes_running_event(monkeypatch):
    from app.models.case import RunStatus, TestCase, TestRun

    run = _Obj(id=1, case_id=10, trace_id=None, parent_run_id=None, status=RunStatus.pending)
    case = _Obj(id=10, dataset_id=None)
    db = _FakeDB({("TestRun", 1): run, ("TestCase", 10): case})
    _install_session(monkeypatch, db)
    events = _publish_recorder(monkeypatch)

    async def fake_dispatch(_db, run_obj, _case, _extra):
        run_obj.status = RunStatus.passed
        return True

    monkeypatch.setattr(tasks, "dispatch_case", fake_dispatch)

    tasks.run_test_case(None, 1, {}, trace_id="trace-x")

    assert run.trace_id == "trace-x"
    assert run.status is RunStatus.passed
    assert [e["type"] for e in events] == ["run_status"]
    assert TestRun and TestCase  # 真模型可导入（防 stub 泄漏）


def test_run_test_case_publishes_error_when_dispatch_reports_failure(monkeypatch):
    from app.models.case import RunStatus

    run = _Obj(id=2, case_id=10, trace_id="t", parent_run_id=None, status=RunStatus.pending)
    db = _FakeDB({("TestRun", 2): run, ("TestCase", 10): _Obj(id=10, dataset_id=None)})
    _install_session(monkeypatch, db)
    events = _publish_recorder(monkeypatch)

    async def fake_dispatch(_db, _run, _case, _extra):
        return False

    monkeypatch.setattr(tasks, "dispatch_case", fake_dispatch)

    tasks.run_test_case(None, 2, {})

    assert [e["type"] for e in events] == ["run_status", "completed"]
    assert events[-1]["status"] == "error"


def test_run_test_case_marks_error_when_dispatch_raises(monkeypatch):
    from app.models.case import RunStatus

    run = _Obj(id=3, case_id=10, trace_id="t", parent_run_id=None, status=RunStatus.pending)
    db = _FakeDB({("TestRun", 3): run, ("TestCase", 10): _Obj(id=10, dataset_id=None)})
    _install_session(monkeypatch, db)
    events = _publish_recorder(monkeypatch)

    async def broken_dispatch(_db, _run, _case, _extra):
        raise RuntimeError("boom")

    monkeypatch.setattr(tasks, "dispatch_case", broken_dispatch)

    tasks.run_test_case(None, 3, {})

    assert run.status is RunStatus.error and run.error_message == "boom"
    assert events[-1]["type"] == "completed" and events[-1]["status"] == "error"


def test_run_test_case_routes_dataset_bound_parent_to_parameterized(monkeypatch):
    from app.models.case import RunStatus

    run = _Obj(id=4, case_id=10, trace_id="t", parent_run_id=None, status=RunStatus.pending)
    case = _Obj(id=10, dataset_id=77)
    db = _FakeDB({("TestRun", 4): run, ("TestCase", 10): case})
    _install_session(monkeypatch, db)
    routed = []

    async def fake_parameterized(_db, parent_run, case_obj, _extra):
        routed.append((parent_run.id, case_obj.dataset_id))

    monkeypatch.setattr(tasks, "_execute_parameterized", fake_parameterized)

    tasks.run_test_case(None, 4, {})

    assert routed == [(4, 77)]
    assert run.status is RunStatus.pending  # 主流程未接管状态


# ── run_test_suite ──────────────────────────────────────────


def _suite_models():
    from app.models.suite import SuiteRunStatus

    return SuiteRunStatus


def test_run_test_suite_returns_when_suite_run_missing(monkeypatch):
    db = _FakeDB()
    _install_session(monkeypatch, db)

    tasks.run_test_suite(None, 404, {})

    assert db.commits == 0


def test_run_test_suite_marks_error_when_suite_missing(monkeypatch):
    SuiteRunStatus = _suite_models()
    suite_run = _Obj(id=20, suite_id=99, trace_id="t", status=SuiteRunStatus.pending)
    db = _FakeDB({("SuiteRun", 20): suite_run})
    _install_session(monkeypatch, db)

    tasks.run_test_suite(None, 20, {})

    assert suite_run.status is SuiteRunStatus.error
    assert suite_run.error_message == "套件不存在"


def test_run_test_suite_executes_and_notifies_with_html_report(monkeypatch):
    SuiteRunStatus = _suite_models()
    suite_run = _Obj(id=21, suite_id=5, trace_id="t", status=SuiteRunStatus.pending, result_summary=None)
    suite = _Obj(id=5, project_id=3, name="Smoke")
    db = _FakeDB({("SuiteRun", 21): suite_run, ("TestSuite", 5): suite})
    _install_session(monkeypatch, db)
    notifications = []
    _install_notifier(monkeypatch, html_enabled=True, calls=notifications)
    _install_exports(monkeypatch, html="<html>suite</html>")

    async def fake_execute_suite_cases(_db, run_obj, _suite, _extra, **_kwargs):
        run_obj.status = SuiteRunStatus.passed
        run_obj.result_summary = {"total": 2, "passed": 2, "failed": 0, "error": 0}

    monkeypatch.setattr(tasks, "_execute_suite_cases", fake_execute_suite_cases)

    tasks.run_test_suite(None, 21, {})

    assert suite_run.status is SuiteRunStatus.passed
    assert isinstance(suite_run.duration_ms, int)
    assert notifications and notifications[0]["report_html"] == "<html>suite</html>"
    assert notifications[0]["payload"]["entity_type"] == "suite"


def test_run_test_suite_swallows_notification_failures(monkeypatch):
    SuiteRunStatus = _suite_models()
    suite_run = _Obj(id=22, suite_id=5, trace_id="t", status=SuiteRunStatus.pending, result_summary=None)
    db = _FakeDB({("SuiteRun", 22): suite_run, ("TestSuite", 5): _Obj(id=5, project_id=3, name="Smoke")})
    _install_session(monkeypatch, db)
    _install_notifier(monkeypatch, fail=True)

    async def fake_execute_suite_cases(_db, run_obj, _suite, _extra, **_kwargs):
        run_obj.status = SuiteRunStatus.failed
        run_obj.result_summary = {"total": 1, "passed": 0, "failed": 1, "error": 0}

    monkeypatch.setattr(tasks, "_execute_suite_cases", fake_execute_suite_cases)

    tasks.run_test_suite(None, 22, {})

    assert suite_run.status is SuiteRunStatus.failed


# ── _execute_plan_suite / _execute_suite_inline ────────────


def test_execute_plan_suite_returns_error_for_missing_suite(monkeypatch):
    db = _FakeDB()
    _install_session(monkeypatch, db)

    result = asyncio.run(tasks._execute_plan_suite(plan_meta={"trace_id": "t"}, suite_id=404, extra_vars={}))

    assert result == {"suite_id": 404, "suite_run_id": None, "status": "error", "error": "套件不存在"}


def test_execute_plan_suite_creates_run_and_falls_back_to_creator(monkeypatch):
    SuiteRunStatus = _suite_models()
    suite = _Obj(id=6, name="Regression", project_id=3)
    db = _FakeDB({("TestSuite", 6): suite})
    _install_session(monkeypatch, db)

    async def fake_inline(_db, suite_run, _suite, _extra, **_kwargs):
        suite_run.status = SuiteRunStatus.passed

    monkeypatch.setattr(tasks, "_execute_suite_inline", fake_inline)

    result = asyncio.run(
        tasks._execute_plan_suite(
            plan_meta={"triggered_by": None, "creator_id": 42, "trace_id": "t"},
            suite_id=6,
            extra_vars={},
        )
    )

    created = db.added[0]
    assert created.triggered_by == 42 and created.trace_id == "t"
    assert result["status"] == "passed" and result["suite_name"] == "Regression"


def test_execute_plan_suite_marks_error_when_inline_execution_raises(monkeypatch):
    SuiteRunStatus = _suite_models()
    db = _FakeDB({("TestSuite", 7): _Obj(id=7, name="Broken", project_id=3)})
    _install_session(monkeypatch, db)

    async def broken_inline(_db, _suite_run, _suite, _extra, **_kwargs):
        raise RuntimeError("suite blew up")

    monkeypatch.setattr(tasks, "_execute_suite_inline", broken_inline)

    result = asyncio.run(
        tasks._execute_plan_suite(plan_meta={"triggered_by": 1, "trace_id": "t"}, suite_id=7, extra_vars={})
    )

    assert result["status"] == "error"
    assert db.added[0].error_message == "suite blew up"


def test_execute_suite_inline_sets_duration_and_outcome(monkeypatch):
    SuiteRunStatus = _suite_models()
    suite_run = _Obj(id=30, status=SuiteRunStatus.pending)
    outcomes = []

    async def fake_execute_suite_cases(_db, run_obj, _suite, _extra, **_kwargs):
        run_obj.status = SuiteRunStatus.passed

    monkeypatch.setattr(tasks, "_execute_suite_cases", fake_execute_suite_cases)
    monkeypatch.setattr(tasks, "_record_run_outcome", lambda entity, status: outcomes.append((entity, status)))

    asyncio.run(tasks._execute_suite_inline(_FakeDB(), suite_run, _Obj(id=1), {}))

    assert isinstance(suite_run.duration_ms, int)
    assert outcomes == [("suite", SuiteRunStatus.passed)]


# ── run_test_plan ───────────────────────────────────────────


def _plan_models():
    from app.models.plan import PlanRunStatus

    return PlanRunStatus


def _plan_run_stub(plan_id=70):
    PlanRunStatus = _plan_models()
    return _Obj(
        id=60,
        plan_id=plan_id,
        trace_id="trace-plan",
        triggered_by=9,
        status=PlanRunStatus.pending,
        trigger_type=types.SimpleNamespace(value="manual"),
    )


def _plan_stub(**overrides):
    values = dict(
        id=70,
        project_id=3,
        name="Nightly",
        creator_id=1,
        config={"execution_mode": "sequential"},
        suite_ids=[{"suite_id": 1, "sort": 0}, {"suite_id": 2, "sort": 1}],
        auto_create_bugs=False,
        schedule_type=types.SimpleNamespace(value="manual"),
        cron_expression=None,
        env_id=None,
    )
    values.update(overrides)
    return _Obj(**values)


def test_run_test_plan_returns_when_plan_run_missing(monkeypatch):
    db = _FakeDB()
    _install_session(monkeypatch, db)

    tasks.run_test_plan(None, 404, {})

    assert db.commits == 0


def test_run_test_plan_marks_error_when_plan_missing(monkeypatch):
    PlanRunStatus = _plan_models()
    plan_run = _plan_run_stub()
    db = _FakeDB({("PlanRun", 60): plan_run})
    _install_session(monkeypatch, db)

    tasks.run_test_plan(None, 60, {})

    assert plan_run.status is PlanRunStatus.error
    assert plan_run.error_message == "测试计划不存在"


def test_run_test_plan_sequential_success_updates_schedule_and_notifies(monkeypatch):
    PlanRunStatus = _plan_models()
    plan_run = _plan_run_stub()
    plan = _plan_stub(schedule_type=types.SimpleNamespace(value="cron"), cron_expression="*/5 * * * *")
    db = _FakeDB({("PlanRun", 60): plan_run, ("TestPlan", 70): plan})
    _install_session(monkeypatch, db)
    notifications = []
    _install_notifier(monkeypatch, calls=notifications)

    async def fake_plan_suite(*, plan_meta, suite_id, extra_vars, **_kwargs):
        return {"suite_id": suite_id, "suite_run_id": 100 + suite_id, "status": "passed"}

    monkeypatch.setattr(tasks, "_execute_plan_suite", fake_plan_suite)

    tasks.run_test_plan(None, 60, {})

    assert plan_run.status is PlanRunStatus.passed
    assert [r["status"] for r in plan_run.suite_run_ids] == ["passed", "passed"]
    assert plan_run.result_summary["passed"] == 2
    assert plan.last_run_at is not None and plan.next_run_at is not None
    assert notifications[0]["payload"]["entity_type"] == "plan"


def test_run_test_plan_fast_fail_marks_remaining_suites_skipped(monkeypatch):
    PlanRunStatus = _plan_models()
    plan_run = _plan_run_stub()
    plan = _plan_stub(config={"execution_mode": "sequential", "fail_strategy": "fast-fail"})
    db = _FakeDB({("PlanRun", 60): plan_run, ("TestPlan", 70): plan})
    _install_session(monkeypatch, db)
    _install_notifier(monkeypatch)

    async def fake_plan_suite(*, plan_meta, suite_id, extra_vars, **_kwargs):
        return {"suite_id": suite_id, "suite_run_id": 100 + suite_id, "status": "failed"}

    monkeypatch.setattr(tasks, "_execute_plan_suite", fake_plan_suite)

    tasks.run_test_plan(None, 60, {})

    assert plan_run.status is PlanRunStatus.failed
    statuses = {r["suite_id"]: r["status"] for r in plan_run.suite_run_ids}
    assert statuses == {1: "failed", 2: "skipped"}


def test_run_test_plan_parallel_mode_executes_all_batches(monkeypatch):
    PlanRunStatus = _plan_models()
    plan_run = _plan_run_stub()
    plan = _plan_stub(config={"execution_mode": "parallel", "max_workers": 2})
    db = _FakeDB({("PlanRun", 60): plan_run, ("TestPlan", 70): plan})
    _install_session(monkeypatch, db)
    _install_notifier(monkeypatch)
    seen = []

    async def fake_plan_suite(*, plan_meta, suite_id, extra_vars, **_kwargs):
        seen.append(suite_id)
        await asyncio.sleep(0)
        return {"suite_id": suite_id, "suite_run_id": 100 + suite_id, "status": "passed"}

    monkeypatch.setattr(tasks, "_execute_plan_suite", fake_plan_suite)

    tasks.run_test_plan(None, 60, {})

    assert sorted(seen) == [1, 2]
    assert plan_run.status is PlanRunStatus.passed


def test_run_test_plan_records_auto_bug_pipeline_failure(monkeypatch):
    PlanRunStatus = _plan_models()
    plan_run = _plan_run_stub()
    plan = _plan_stub(auto_create_bugs=True)

    # auto_bugs 分支第一步 db.execute 查询 BugTracker —— 让它爆炸走 auto_bugs_error 路径
    class _ExplodingDB(_FakeDB):
        async def execute(self, _query):
            raise RuntimeError("tracker query failed")

    db = _ExplodingDB({("PlanRun", 60): plan_run, ("TestPlan", 70): plan})
    _install_session(monkeypatch, db)
    _install_notifier(monkeypatch)

    async def fake_plan_suite(*, plan_meta, suite_id, extra_vars, **_kwargs):
        return {"suite_id": suite_id, "suite_run_id": 100 + suite_id, "status": "failed"}

    monkeypatch.setattr(tasks, "_execute_plan_suite", fake_plan_suite)

    tasks.run_test_plan(None, 60, {})

    assert plan_run.result_summary["auto_bugs_error"] == "tracker query failed"
    assert plan_run.status is PlanRunStatus.failed


def test_run_test_plan_swallows_notification_failures(monkeypatch):
    PlanRunStatus = _plan_models()
    plan_run = _plan_run_stub()
    plan = _plan_stub(suite_ids=[{"suite_id": 1, "sort": 0}])
    db = _FakeDB({("PlanRun", 60): plan_run, ("TestPlan", 70): plan})
    _install_session(monkeypatch, db)
    _install_notifier(monkeypatch, fail=True)

    async def fake_plan_suite(*, plan_meta, suite_id, extra_vars, **_kwargs):
        return {"suite_id": suite_id, "suite_run_id": 101, "status": "passed"}

    monkeypatch.setattr(tasks, "_execute_plan_suite", fake_plan_suite)

    tasks.run_test_plan(None, 60, {})

    assert plan_run.status is PlanRunStatus.passed


# ── check_cron_plans ────────────────────────────────────────


def test_check_cron_plans_triggers_due_plan_and_advances_schedule(monkeypatch):
    plan = _plan_stub(cron_expression="*/5 * * * *", next_run_at=None, is_enabled=True)
    db = _FakeDB(execute_rows=[[plan]])
    _install_session(monkeypatch, db)
    delayed = []
    monkeypatch.setattr(tasks.run_test_plan, "delay", lambda *args: delayed.append(args), raising=False)

    tasks.check_cron_plans()

    assert len(delayed) == 1
    plan_run = db.added[0]
    assert plan_run.trigger_type.value == "cron"
    assert plan.next_run_at is not None and plan.is_enabled is True


def test_check_cron_plans_skips_plans_without_suites(monkeypatch):
    plan = _plan_stub(suite_ids=[], cron_expression="*/5 * * * *")
    db = _FakeDB(execute_rows=[[plan]])
    _install_session(monkeypatch, db)
    delayed = []
    monkeypatch.setattr(tasks.run_test_plan, "delay", lambda *args: delayed.append(args), raising=False)

    tasks.check_cron_plans()

    assert delayed == [] and db.added == []


def test_check_cron_plans_disables_plan_with_invalid_cron(monkeypatch):
    plan = _plan_stub(cron_expression="not a cron", is_enabled=True)
    db = _FakeDB(execute_rows=[[plan]])
    _install_session(monkeypatch, db)
    delayed = []
    monkeypatch.setattr(tasks.run_test_plan, "delay", lambda *args: delayed.append(args), raising=False)

    tasks.check_cron_plans()

    assert plan.is_enabled is False
    assert len(delayed) == 1  # 计划仍按本次到期触发，只是不再排下一次


def test_check_cron_plans_merges_environment_variables(monkeypatch):
    env = _Obj(id=8)
    plan = _plan_stub(cron_expression="*/5 * * * *", env_id=8)
    db = _FakeDB(objects={("Environment", 8): env}, execute_rows=[[plan], [_Obj(id=1, key="k")]])
    _install_session(monkeypatch, db)
    delayed = []
    monkeypatch.setattr(tasks.run_test_plan, "delay", lambda *args: delayed.append(args), raising=False)
    monkeypatch.setattr(tasks, "decrypt_env_vars", lambda _values: {"BASE_URL": "https://staging"})

    tasks.check_cron_plans()

    assert delayed[0][1] == {"BASE_URL": "https://staging"}


# ── check_dashboard_alerts ──────────────────────────────────


def test_check_dashboard_alerts_returns_evaluation_result(monkeypatch):
    db = _FakeDB()
    _install_session(monkeypatch, db)

    async def evaluate(_db):
        return {"triggered": 2}

    monkeypatch.setitem(
        sys.modules, "app.services.dashboard_alerts", types.SimpleNamespace(evaluate_dashboard_alerts=evaluate)
    )

    assert tasks.check_dashboard_alerts() == {"triggered": 2}


def test_check_dashboard_alerts_reports_error_shape_on_failure(monkeypatch):
    def broken_session():
        raise RuntimeError("db gone")

    monkeypatch.setattr(sys.modules["app.core.database"], "AsyncSessionLocal", broken_session, raising=False)

    async def evaluate(_db):  # pragma: no cover - 不应被调用
        return {}

    monkeypatch.setitem(
        sys.modules, "app.services.dashboard_alerts", types.SimpleNamespace(evaluate_dashboard_alerts=evaluate)
    )

    assert tasks.check_dashboard_alerts() == {"error": True}
