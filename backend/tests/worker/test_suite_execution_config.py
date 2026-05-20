import asyncio
import importlib
import sys
import types
from pathlib import Path

_REAL_BOOTSTRAP = importlib.import_module("app.models.bootstrap")
_REAL_TRACING = importlib.import_module("app.core.tracing")
_REAL_CASE_MODELS = importlib.import_module("app.models.case")
_REAL_SUITE_MODELS = importlib.import_module("app.models.suite")
_REAL_CASE_DISPATCH = importlib.import_module("app.worker.case_dispatch")
_REAL_ENCRYPTION = importlib.import_module("app.core.encryption")

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))


class FakeCeleryApp:
    def task(self, *args, **kwargs):
        def decorator(func):
            return func

        return decorator


sys.modules["app.worker.celery_app"] = types.SimpleNamespace(celery_app=FakeCeleryApp())
sys.modules["app.worker.case_dispatch"] = types.SimpleNamespace(dispatch_case=None)
sys.modules["app.models.bootstrap"] = types.SimpleNamespace(load_all_models=lambda: None)
sys.modules["app.core.redis_client"] = types.SimpleNamespace(
    publish_run_event=None,
    delete_json_cache_pattern=None,
    get_json_cache=lambda *args, **kwargs: None,
    set_json_cache=lambda *args, **kwargs: None,
    delete_json_cache=lambda *args, **kwargs: None,
)
sys.modules["app.core.encryption"] = types.SimpleNamespace(decrypt_env_vars=lambda values: values)
sys.modules["app.core.tracing"] = types.SimpleNamespace(
    get_trace_id=lambda: None,
    generate_trace_id=lambda: "trace-suite",
    set_trace_id=lambda value: value,
    reset_trace_id=lambda _token: None,
    attach_app_trace_id_to_current_span=lambda *args, **kwargs: None,
)
sys.modules["app.worker.async_runner"] = types.SimpleNamespace(run_async=lambda coro: None)
sys.modules.pop("app.worker.tasks", None)

from app.worker import tasks

sys.modules["app.models.bootstrap"] = _REAL_BOOTSTRAP
sys.modules["app.core.tracing"] = _REAL_TRACING
sys.modules["app.worker.case_dispatch"] = _REAL_CASE_DISPATCH
sys.modules["app.core.encryption"] = _REAL_ENCRYPTION


class _FakeRunStatusValue:
    def __init__(self, value: str):
        self.value = value


class _FakeRunStatus:
    pending = _FakeRunStatusValue("pending")
    running = _FakeRunStatusValue("running")
    passed = _FakeRunStatusValue("passed")
    failed = _FakeRunStatusValue("failed")
    error = _FakeRunStatusValue("error")


class _FakeSuiteRunStatus:
    passed = "passed"
    failed = "failed"


class _FakeCase:
    def __init__(self, case_id: int, name: str):
        self.id = case_id
        self.name = name


class _FakeDB:
    def __init__(self, cases: dict[int, _FakeCase]):
        self.cases = cases

    async def get(self, model, pk):
        if getattr(model, "__name__", "") == "TestCase":
            return self.cases.get(pk)
        return None


class _FakeSuiteRun:
    def __init__(self):
        self.status = None
        self.case_run_ids = []
        self.result_summary = {}
        self.trace_id = "trace-suite"
        self.triggered_by = 7
        self.environment = None


class _FakeSuite:
    def __init__(self, case_ids, config):
        self.case_ids = case_ids
        self.config = config


def test_normalize_suite_config_falls_back_to_safe_defaults():
    result = tasks._normalize_suite_config({
        "execution_mode": "invalid",
        "max_workers": "x",
        "fail_strategy": "unknown",
        "min_pass_rate": "oops",
    })

    assert result == {
        "execution_mode": "sequential",
        "max_workers": 5,
        "fail_strategy": "continue",
        "min_pass_rate": 0.8,
    }


def test_suite_run_should_stop_for_fast_fail():
    should_stop = tasks._suite_run_should_stop(
        {"total": 1, "passed": 0, "failed": 1, "error": 0, "skipped": 0},
        3,
        "fast-fail",
        0.8,
    )

    assert should_stop is True


def test_suite_run_should_stop_for_minimum_pass_rate():
    should_stop = tasks._suite_run_should_stop(
        {"total": 2, "passed": 0, "failed": 2, "error": 0, "skipped": 0},
        3,
        "require-minimum-pass-rate",
        0.5,
    )

    assert should_stop is True


def test_execute_suite_cases_marks_remaining_cases_skipped_on_fast_fail(monkeypatch):
    monkeypatch.setitem(sys.modules, "app.models.case", types.SimpleNamespace(TestCase=type("TestCase", (), {})))
    monkeypatch.setitem(sys.modules, "app.models.suite", types.SimpleNamespace(SuiteRunStatus=_FakeSuiteRunStatus))

    results = {
        1: {"case_id": 1, "case_name": "Case-1", "run_id": 101, "status": "failed"},
        2: {"case_id": 2, "case_name": "Case-2", "run_id": 102, "status": "passed"},
        3: {"case_id": 3, "case_name": "Case-3", "run_id": 103, "status": "passed"},
    }

    async def fake_execute_case_run(_db, _suite_run, case, _extra_vars):
        return results[case.id]

    monkeypatch.setattr(tasks, "_execute_case_run", fake_execute_case_run)

    suite_run = _FakeSuiteRun()
    suite = _FakeSuite(
        case_ids=[
            {"case_id": 1, "sort": 0},
            {"case_id": 2, "sort": 1},
            {"case_id": 3, "sort": 2},
        ],
        config={"execution_mode": "sequential", "fail_strategy": "fast-fail"},
    )
    db = _FakeDB({
        1: _FakeCase(1, "Case-1"),
        2: _FakeCase(2, "Case-2"),
        3: _FakeCase(3, "Case-3"),
    })

    asyncio.run(tasks._execute_suite_cases(db, suite_run, suite, {}))

    assert suite_run.status == "failed"
    assert suite_run.result_summary["failed"] == 1
    assert suite_run.result_summary["skipped"] == 2
    assert suite_run.case_run_ids[1]["status"] == "skipped"
    assert suite_run.case_run_ids[2]["status"] == "skipped"


def test_execute_suite_cases_uses_parallel_batches_and_collects_results(monkeypatch):
    monkeypatch.setitem(sys.modules, "app.models.case", types.SimpleNamespace(TestCase=type("TestCase", (), {})))
    monkeypatch.setitem(sys.modules, "app.models.suite", types.SimpleNamespace(SuiteRunStatus=_FakeSuiteRunStatus))

    started: list[int] = []

    async def fake_execute_case_run(_db, _suite_run, case, _extra_vars):
        started.append(case.id)
        await asyncio.sleep(0)
        return {"case_id": case.id, "case_name": case.name, "run_id": 100 + case.id, "status": "passed"}

    monkeypatch.setattr(tasks, "_execute_case_run", fake_execute_case_run)

    suite_run = _FakeSuiteRun()
    suite = _FakeSuite(
        case_ids=[
            {"case_id": 1, "sort": 0},
            {"case_id": 2, "sort": 1},
            {"case_id": 3, "sort": 2},
        ],
        config={"execution_mode": "parallel", "max_workers": 2, "fail_strategy": "continue"},
    )
    db = _FakeDB({
        1: _FakeCase(1, "Case-1"),
        2: _FakeCase(2, "Case-2"),
        3: _FakeCase(3, "Case-3"),
    })

    asyncio.run(tasks._execute_suite_cases(db, suite_run, suite, {}))

    assert started == [1, 2, 3]
    assert suite_run.status == "passed"
    assert suite_run.result_summary["passed"] == 3
    assert suite_run.result_summary["execution_mode"] == "parallel"
    assert suite_run.result_summary["max_workers"] == 2
