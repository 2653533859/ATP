import asyncio
import importlib
import sys
import types
from pathlib import Path

_REAL_BOOTSTRAP = importlib.import_module("app.models.bootstrap")
_REAL_TRACING = importlib.import_module("app.core.tracing")
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
    generate_trace_id=lambda: "trace-plan",
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


def test_normalize_plan_config_defaults_to_sequential_with_max_workers_3():
    result = tasks._normalize_plan_config(None)

    assert result == {
        "execution_mode": "sequential",
        "max_workers": 3,
        "fail_strategy": "continue",
        "min_pass_rate": 0.8,
    }


def test_normalize_plan_config_falls_back_on_invalid_values():
    result = tasks._normalize_plan_config({
        "execution_mode": "weird",
        "max_workers": "x",
        "fail_strategy": "wrong",
        "min_pass_rate": "oops",
    })

    assert result == {
        "execution_mode": "sequential",
        "max_workers": 3,
        "fail_strategy": "continue",
        "min_pass_rate": 0.8,
    }


def test_normalize_plan_config_caps_max_workers_at_10():
    result = tasks._normalize_plan_config({"max_workers": 999})
    assert result["max_workers"] == 10

    result = tasks._normalize_plan_config({"max_workers": 0})
    assert result["max_workers"] == 1


def test_normalize_plan_config_preserves_valid_parallel_settings():
    result = tasks._normalize_plan_config({
        "execution_mode": "parallel",
        "max_workers": 5,
        "fail_strategy": "fast-fail",
        "min_pass_rate": 0.5,
    })

    assert result == {
        "execution_mode": "parallel",
        "max_workers": 5,
        "fail_strategy": "fast-fail",
        "min_pass_rate": 0.5,
    }


def test_plan_run_should_stop_for_fast_fail():
    assert tasks._plan_run_should_stop(
        {"total": 1, "passed": 0, "failed": 1, "error": 0},
        3,
        "fast-fail",
        0.8,
    ) is True


def test_plan_run_should_stop_for_minimum_pass_rate():
    # 已跑 2 个，全失败；剩 1 个，最大可能通过率 1/3 < 0.5，应当停止
    assert tasks._plan_run_should_stop(
        {"total": 2, "passed": 0, "failed": 2, "error": 0},
        3,
        "require-minimum-pass-rate",
        0.5,
    ) is True


def test_plan_run_should_stop_returns_false_for_continue():
    assert tasks._plan_run_should_stop(
        {"total": 1, "passed": 0, "failed": 1, "error": 0},
        3,
        "continue",
        0.8,
    ) is False


def test_execute_plan_suite_returns_error_when_suite_missing(monkeypatch):
    class _FakeSession:
        def __init__(self):
            self.added = []

        async def __aenter__(self):
            return self

        async def __aexit__(self, *exc):
            return False

        async def get(self, _model, _pk):
            return None

        def add(self, obj):
            self.added.append(obj)

        async def commit(self):
            return None

        async def refresh(self, _obj):
            return None

    fake_session = _FakeSession()

    fake_db_module = types.SimpleNamespace(AsyncSessionLocal=lambda: fake_session)
    fake_suite_module = types.SimpleNamespace(
        TestSuite=type("TestSuite", (), {}),
        SuiteRun=type("SuiteRun", (), {"__init__": lambda self, **kw: None}),
        SuiteRunStatus=types.SimpleNamespace(pending="pending"),
    )
    monkeypatch.setitem(sys.modules, "app.core.database", fake_db_module)
    monkeypatch.setitem(sys.modules, "app.models.suite", fake_suite_module)

    plan_meta = {"triggered_by": 9, "creator_id": 1, "trace_id": "trace-x"}

    result = asyncio.run(
        tasks._execute_plan_suite(plan_meta=plan_meta, suite_id=42, extra_vars={})
    )

    assert result == {
        "suite_id": 42,
        "suite_run_id": None,
        "status": "error",
        "error": "套件不存在",
    }
    assert fake_session.added == []
