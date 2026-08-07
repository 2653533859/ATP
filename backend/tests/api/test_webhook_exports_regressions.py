import asyncio
import importlib
import sys
import types
import xml.etree.ElementTree as ET
from pathlib import Path

import pytest
from fastapi import HTTPException
from starlette.requests import Request

_REAL_TRACING = importlib.import_module("app.core.tracing")

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

sys.modules["app.core.database"] = types.SimpleNamespace(get_db=lambda: None)


def _p3c_noop(*_a, **_kw):
    return None


async def _p3c_noop_async(*_a, **_kw):
    return None


sys.modules["app.api.deps"] = types.SimpleNamespace(
    get_current_user=lambda: None,
    require_engineer=lambda: None,
    require_admin=_p3c_noop,
    require_project_access=lambda *a, **kw: _p3c_noop,
    assert_project_access=_p3c_noop_async,
    ProjectRole=type("ProjectRole", (), {"owner": "owner", "editor": "editor", "viewer": "viewer"}),
)
sys.modules["app.core.minio_client"] = types.SimpleNamespace(read_bytes=lambda *_args, **_kwargs: b"")
sys.modules["app.core.rate_limit"] = types.SimpleNamespace(
    limiter=types.SimpleNamespace(limit=lambda *_args, **_kwargs: (lambda func: func))
)
sys.modules["app.core.tracing"] = types.SimpleNamespace(
    get_trace_id=lambda: None,
    generate_trace_id=lambda: "trace-test",
    set_trace_id=lambda value: value,
    reset_trace_id=lambda _token: None,
)

from app.api.v1 import exports, webhook

sys.modules["app.core.tracing"] = _REAL_TRACING


def _fake_request() -> Request:
    return Request(
        {
            "type": "http",
            "method": "POST",
            "path": "/webhook/trigger",
            "headers": [],
        }
    )


class _FakeScalarResult:
    def __init__(self, values):
        self._values = values

    def all(self):
        return self._values


class _FakeExecuteResult:
    def __init__(self, values):
        self._values = values

    def scalars(self):
        return _FakeScalarResult(self._values)


class _FakeSuite:
    def __init__(self, suite_id: int = 11, creator_id: int = 42, case_ids=None):
        self.id = suite_id
        self.creator_id = creator_id
        self.case_ids = case_ids if case_ids is not None else [{"case_id": 1, "sort": 0}]


class _FakePlan:
    def __init__(self, plan_id: int = 21, suite_ids=None):
        self.id = plan_id
        self.suite_ids = suite_ids if suite_ids is not None else [{"suite_id": 1, "sort": 0}]


class _FakeRun:
    def __init__(self, run_id: int = 5, status: str = "failed", error_message: str = "run failed"):
        self.id = run_id
        self.status = types.SimpleNamespace(value=status)
        self.error_message = error_message
        self.duration_ms = 0


class _FakeSuiteRun:
    def __init__(self, **kwargs):
        for k, v in kwargs.items():
            setattr(self, k, v)
        self.id = kwargs.get("id")


class _FakePlanRun:
    def __init__(self, **kwargs):
        for k, v in kwargs.items():
            setattr(self, k, v)
        self.id = kwargs.get("id")


class _FakeWebhookDB:
    def __init__(self, suite=None, env=None, plan=None, performance_test=None):
        self._suite = suite
        self._env = env
        self._plan = plan
        self._performance_test = performance_test
        self.added = []

    async def get(self, model, _pk):
        model_name = getattr(model, "__name__", "")
        if model_name == "TestSuite":
            return self._suite
        if model_name == "TestPlan":
            return self._plan
        if model_name == "Environment":
            return self._env
        if model_name == "PerformanceTest":
            return self._performance_test
        return None

    async def execute(self, _query):
        return _FakeExecuteResult([])

    def add(self, obj):
        self.added.append(obj)

    async def commit(self):
        return None

    async def refresh(self, obj):
        if getattr(obj, "id", None) is None:
            obj.id = 1001


class _FakeExportDB:
    def __init__(self, run):
        self._run = run

    async def get(self, model, _pk):
        model_name = getattr(model, "__name__", "")
        if model_name == "TestRun":
            return self._run
        return None

    async def execute(self, _query):
        return _FakeExecuteResult([])


def test_webhook_suite_trigger_uses_valid_user_reference(monkeypatch):
    delayed = {}
    monkeypatch.setattr(webhook, "SuiteRun", _FakeSuiteRun)
    monkeypatch.setattr(webhook, "get_trace_id", lambda: "trace-webhook-suite")
    monkeypatch.setitem(
        sys.modules,
        "app.worker.tasks",
        types.SimpleNamespace(
            run_test_suite=types.SimpleNamespace(
                delay=lambda run_id, extra_vars, trace_id: delayed.update(
                    run_id=run_id,
                    extra_vars=extra_vars,
                    trace_id=trace_id,
                )
            )
        ),
    )

    db = _FakeWebhookDB(suite=_FakeSuite(creator_id=99), env=None)
    body = webhook.WebhookTriggerBody(target_type="suite", target_id=11, extra_vars={"branch": "main"})

    asyncio.run(webhook.webhook_trigger(request=_fake_request(), body=body, db=db, _api_key="ok"))

    assert db.added, "应创建 SuiteRun"
    assert db.added[0].triggered_by == 99
    assert db.added[0].trace_id == "trace-webhook-suite"
    assert delayed == {"run_id": 1001, "extra_vars": {"branch": "main"}, "trace_id": "trace-webhook-suite"}


def test_webhook_plan_trigger_passes_trace_id(monkeypatch):
    delayed = {}
    monkeypatch.setattr(webhook, "PlanRun", _FakePlanRun)
    monkeypatch.setattr(webhook, "get_trace_id", lambda: "trace-webhook-plan")
    monkeypatch.setitem(
        sys.modules,
        "app.worker.tasks",
        types.SimpleNamespace(
            run_test_plan=types.SimpleNamespace(
                delay=lambda run_id, extra_vars, trace_id: delayed.update(
                    run_id=run_id,
                    extra_vars=extra_vars,
                    trace_id=trace_id,
                )
            )
        ),
    )

    db = _FakeWebhookDB(plan=_FakePlan(), env=None)
    body = webhook.WebhookTriggerBody(target_type="plan", target_id=21, extra_vars={"commit": "abc"})

    result = asyncio.run(webhook.webhook_trigger(request=_fake_request(), body=body, db=db, _api_key="ok"))

    assert result.run_id == 1001
    assert db.added[0].trace_id == "trace-webhook-plan"
    assert delayed == {"run_id": 1001, "extra_vars": {"commit": "abc"}, "trace_id": "trace-webhook-plan"}


def test_webhook_trigger_rejects_unknown_env_id():
    db = _FakeWebhookDB(suite=_FakeSuite(), env=None)
    body = webhook.WebhookTriggerBody(target_type="suite", target_id=11, env_id=999, extra_vars={})

    with pytest.raises(HTTPException) as exc:
        asyncio.run(webhook.webhook_trigger(request=_fake_request(), body=body, db=db, _api_key="ok"))

    assert exc.value.status_code == 404


def test_webhook_performance_trigger_uses_encrypted_runtime_snapshot(monkeypatch):
    delayed = []

    class _FakePerformanceRun:
        def __init__(self, **kwargs):
            self.__dict__.update(kwargs)
            self.id = None

    monkeypatch.setattr(webhook, "PerformanceRun", _FakePerformanceRun)
    monkeypatch.setitem(
        sys.modules,
        "app.worker.tasks_performance",
        types.SimpleNamespace(
            run_performance_test=types.SimpleNamespace(delay=delayed.append),
        ),
    )
    test = types.SimpleNamespace(
        id=31,
        project_id=2,
        default_options={"vus": 3},
    )
    db = _FakeWebhookDB(performance_test=test)
    body = webhook.WebhookTriggerBody(
        target_type="performance_test",
        target_id=test.id,
        extra_vars={"API_TOKEN": "secret"},
        options={"duration": "30s"},
    )

    result = asyncio.run(webhook.webhook_trigger(request=_fake_request(), body=body, db=db, _api_key="ok"))

    assert result.target_type == "performance_test"
    assert delayed == [1001]
    run = db.added[0]
    assert run.options_snapshot["vus"] == 3
    assert run.options_snapshot["duration"] == "30s"
    assert "API_TOKEN" not in run.options_snapshot.get("env", {})
    assert "__environment_values_encrypted" in run.options_snapshot


def test_webhook_performance_trigger_passes_executor_to_validation_and_node_selection(monkeypatch):
    calls = {}

    class _FakePerformanceRun:
        def __init__(self, **kwargs):
            self.__dict__.update(kwargs)
            self.id = None

    monkeypatch.setattr(webhook, "PerformanceRun", _FakePerformanceRun)
    monkeypatch.setitem(
        sys.modules,
        "app.worker.tasks_performance",
        types.SimpleNamespace(run_performance_test=types.SimpleNamespace(delay=lambda _run_id: None)),
    )

    from app.api.v1 import performance

    monkeypatch.setattr(
        performance,
        "_validate_performance_options",
        lambda _options, executor="k6": calls.update(validation=executor),
    )

    async def fake_resolve(_db, _node_id, _options, executor="k6"):
        calls["node"] = executor
        return None

    monkeypatch.setattr(performance, "_resolve_performance_node", fake_resolve)

    test = types.SimpleNamespace(
        id=32,
        project_id=2,
        default_options={"target": "https://example.test"},
        executor="grpc",
    )
    db = _FakeWebhookDB(performance_test=test)
    body = webhook.WebhookTriggerBody(target_type="performance_test", target_id=test.id)

    asyncio.run(webhook.webhook_trigger(request=_fake_request(), body=body, db=db, _api_key="ok"))

    assert calls == {"validation": "grpc", "node": "grpc"}


def test_export_run_junit_reports_run_failure_without_steps():
    run = _FakeRun(status="failed", error_message="executor bootstrap failed")
    db = _FakeExportDB(run=run)

    response = asyncio.run(exports.export_run_junit(run_id=5, db=db, _=None))
    root = ET.fromstring(response.body.decode("utf-8"))
    testsuite = root.find("testsuite")

    assert testsuite is not None
    assert testsuite.attrib["tests"] == "1"
    assert testsuite.attrib["failures"] == "1"

    testcase = testsuite.find("testcase")
    assert testcase is not None
    failure = testcase.find("failure")
    assert failure is not None
    assert "executor bootstrap failed" in (failure.attrib.get("message") or "")


def test_extract_minio_object_supports_presigned_url_and_object_key():
    assert exports._extract_minio_object("screenshots/runs/1/step_0.png") == "screenshots/runs/1/step_0.png"
    assert (
        exports._extract_minio_object("http://minio:9000/atp/screenshots/runs/1/step_0.png?X-Amz-Signature=abc")
        == "screenshots/runs/1/step_0.png"
    )


def test_build_report_html_renders_single_run_report():
    run = _FakeRun(status="passed", error_message="")
    run.created_at = None
    step = types.SimpleNamespace(
        step_index=0,
        name="打开页面",
        status=types.SimpleNamespace(value="passed"),
        duration_ms=120,
        request_data=None,
        response_data=None,
        error_message=None,
        screenshot_url=None,
    )

    html = asyncio.run(exports._build_report_html(run, [step], "登录用例", "web"))

    assert "登录用例" in html
    assert "打开页面" in html
