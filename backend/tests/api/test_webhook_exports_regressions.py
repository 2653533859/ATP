import asyncio
import sys
import types
import xml.etree.ElementTree as ET
from pathlib import Path

import pytest
from fastapi import HTTPException
from starlette.requests import Request

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

sys.modules["app.core.database"] = types.SimpleNamespace(get_db=lambda: None)
sys.modules["app.api.deps"] = types.SimpleNamespace(
    get_current_user=lambda: None,
    require_engineer=lambda: None,
)

from app.api.v1 import exports, webhook


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


class _FakeWebhookDB:
    def __init__(self, suite=None, env=None):
        self._suite = suite
        self._env = env
        self.added = []

    async def get(self, model, _pk):
        model_name = getattr(model, "__name__", "")
        if model_name == "TestSuite":
            return self._suite
        if model_name == "Environment":
            return self._env
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
    monkeypatch.setattr(webhook, "SuiteRun", _FakeSuiteRun)
    monkeypatch.setitem(
        sys.modules,
        "app.worker.tasks",
        types.SimpleNamespace(
            run_test_suite=types.SimpleNamespace(delay=lambda *_args, **_kwargs: None)
        ),
    )

    db = _FakeWebhookDB(suite=_FakeSuite(creator_id=99), env=None)
    body = webhook.WebhookTriggerBody(target_type="suite", target_id=11, extra_vars={})

    asyncio.run(webhook.webhook_trigger(request=_fake_request(), body=body, db=db, _api_key="ok"))

    assert db.added, "应创建 SuiteRun"
    assert db.added[0].triggered_by == 99


def test_webhook_trigger_rejects_unknown_env_id():
    db = _FakeWebhookDB(suite=_FakeSuite(), env=None)
    body = webhook.WebhookTriggerBody(
        target_type="suite", target_id=11, env_id=999, extra_vars={}
    )

    with pytest.raises(HTTPException) as exc:
        asyncio.run(webhook.webhook_trigger(request=_fake_request(), body=body, db=db, _api_key="ok"))

    assert exc.value.status_code == 404


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
