import asyncio
import pytest
from app.models.bootstrap import load_all_models
from app.models.case import CaseType, RunStatus

load_all_models()
from app.worker.case_dispatch import _is_multiprotocol_case
from app.worker.executors.multiprotocol_executor import (
    _execute_http_step,
    evaluate_assertion,
    extract_json_value,
    render_dict,
    render_template,
    run_multiprotocol_case,
)


class _FakeDB:
    def __init__(self):
        self.added = []
        self.commit_count = 0

    def add(self, item):
        self.added.append(item)

    async def commit(self):
        self.commit_count += 1


class _FakeRun:
    def __init__(self, run_id=10):
        self.id = run_id
        self.status = RunStatus.running
        self.duration_ms = None


class _FakeCase:
    def __init__(self, config=None, case_type=CaseType.api):
        self.id = 1
        self.case_type = case_type
        self.config = config or {}


def test_multiprotocol_template_rendering():
    ctx = {"order_id": "ORD-123", "user_id": 42}
    # String
    assert render_template("https://api.test/orders/{{order_id}}", ctx) == "https://api.test/orders/ORD-123"
    assert render_template("plain_text", ctx) == "plain_text"

    # Dict
    data = {
        "url": "/user/{{user_id}}",
        "nested": {"key": "{{order_id}}"},
        "list": ["{{user_id}}", "constant"],
    }
    rendered = render_dict(data, ctx)
    assert rendered["url"] == "/user/42"
    assert rendered["nested"]["key"] == "ORD-123"
    assert rendered["list"] == ["42", "constant"]


def test_multiprotocol_assertion_evaluation():
    # eq
    passed, msg = evaluate_assertion({"operator": "eq", "expected": 200}, 200)
    assert passed and msg is None
    passed, msg = evaluate_assertion({"operator": "eq", "expected": 200}, 500)
    assert not passed and "断言失败" in (msg or "")

    # contains
    passed, msg = evaluate_assertion({"operator": "contains", "expected": "success"}, "order success")
    assert passed and msg is None

    # exists
    passed, msg = evaluate_assertion({"operator": "exists"}, "data")
    assert passed and msg is None
    passed, msg = evaluate_assertion({"operator": "exists"}, None)
    assert not passed and "断言失败" in (msg or "")


def test_extract_json_value():
    payload = {"data": {"order": {"id": 888, "items": [{"name": "item-A"}]}}}
    assert extract_json_value(payload, "data.order.id") == 888
    assert extract_json_value(payload, "data.order.items.0.name") == "item-A"
    assert extract_json_value(payload, "missing.key") is None


def test_is_multiprotocol_case_detection():
    # Regular HTTP API case -> False
    case1 = _FakeCase({"steps": [{"name": "s1", "method": "GET"}]})
    assert not _is_multiprotocol_case(case1)

    # Mixed protocol with websocket step -> True
    case2 = _FakeCase(
        {
            "steps": [
                {"name": "s1", "protocol": "http", "method": "POST"},
                {"name": "s2", "protocol": "websocket", "url": "ws://example.test"},
            ]
        }
    )
    assert _is_multiprotocol_case(case2)

    # Explicit flag -> True
    case3 = _FakeCase({"multi_protocol": True, "steps": []})
    assert _is_multiprotocol_case(case3)


def test_multiprotocol_cross_protocol_execution_flow(monkeypatch):
    # Mock redis publish
    published_events = []

    async def fake_publish(_run_id, payload):
        published_events.append(payload)

    monkeypatch.setattr("app.worker.executors.multiprotocol_executor.publish_run_event", fake_publish)

    # Step 1 (HTTP) returns order_id and token
    async def fake_http(step, context):
        assert context.get("INIT_VAR") == "seed"
        return {
            "status_code": 200,
            "body": {"order_id": 555, "auth_token": "token-xyz"},
            "duration_ms": 15,
            "raw_request": {"url": step.get("url")},
        }

    # Step 2 (WebSocket) verifies order_id from Step 1 was passed into parameters!
    async def fake_ws(step, context):
        assert context.get("extracted_order_id") == 555
        assert context.get("extracted_token") == "token-xyz"
        assert "token-xyz" in step.get("url", "")
        return {
            "status_code": 101,
            "body": {"event": "ORDER_CONFIRMED", "order_id": 555},
            "duration_ms": 25,
            "raw_request": {"url": step.get("url")},
        }

    monkeypatch.setattr("app.worker.executors.multiprotocol_executor._execute_http_step", fake_http)
    monkeypatch.setattr("app.worker.executors.multiprotocol_executor._execute_websocket_step", fake_ws)

    db = _FakeDB()
    run = _FakeRun(run_id=20)
    case = _FakeCase(
        config={
            "steps": [
                {
                    "name": "Create Order via HTTP",
                    "protocol": "http",
                    "url": "https://api.test/orders",
                    "extractions": [
                        {"variable": "extracted_order_id", "expression": "order_id"},
                        {"variable": "extracted_token", "expression": "auth_token"},
                    ],
                    "assertions": [{"target": "status_code", "operator": "eq", "expected": 200}],
                },
                {
                    "name": "Listen Order via WebSocket",
                    "protocol": "websocket",
                    "url": "ws://api.test/ws?token={{extracted_token}}",
                    "assertions": [
                        {"target": "status_code", "operator": "eq", "expected": 101},
                        {"target": "event", "operator": "eq", "expected": "ORDER_CONFIRMED"},
                    ],
                },
            ]
        }
    )

    asyncio.run(run_multiprotocol_case(db, run, case, {"INIT_VAR": "seed"}))
    assert run.status == RunStatus.passed
    assert run.duration_ms is not None
    assert len(db.added) == 2
    # Verify both steps were recorded
    assert db.added[0].name == "Create Order via HTTP"
    assert db.added[0].status == RunStatus.passed
    assert db.added[1].name == "Listen Order via WebSocket"
    assert db.added[1].status == RunStatus.passed
    # Completed event published
    assert any(e.get("type") == "completed" and e.get("status") == "passed" for e in published_events)


def _install_fake_httpx(monkeypatch, captured):
    import httpx

    class _FakeResponse:
        status_code = 201
        headers = {"content-type": "application/json"}
        text = '{"ok": true}'

        def json(self):
            return {"ok": True}

    class _FakeAsyncClient:
        def __init__(self, **_kwargs):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *_exc):
            return False

        async def request(self, **kwargs):
            captured.update(kwargs)
            return _FakeResponse()

    monkeypatch.setattr(httpx, "AsyncClient", _FakeAsyncClient)


def test_multiprotocol_http_step_honors_standard_body_and_auth(monkeypatch):
    """标准编辑器的 body_type/auth 形状必须生效，不能只认 json 简写。"""
    from app.worker.executors import multiprotocol_executor as mp

    captured: dict = {}
    _install_fake_httpx(monkeypatch, captured)

    step = {
        "url": "https://api.test/orders/{{order_id}}",
        "method": "post",
        "headers": {"X-Trace": "t-1"},
        "cookies": {"sid": "{{session_id}}"},
        "body_type": "json",
        "body": {"order_id": "{{order_id}}"},
        "auth": {"type": "bearer", "token": "{{token}}"},
    }
    result = asyncio.run(mp._execute_http_step(step, {"order_id": "ORD-1", "session_id": "S-9", "token": "T-7"}))

    assert captured["url"] == "https://api.test/orders/ORD-1"
    assert captured["method"] == "POST"
    assert captured["json"] == {"order_id": "ORD-1"}
    assert captured["headers"]["Authorization"] == "Bearer T-7"
    assert captured["headers"]["X-Trace"] == "t-1"
    assert captured["cookies"] == {"sid": "S-9"}
    assert result["status_code"] == 201
    assert result["raw_request"]["body"] == {"order_id": "ORD-1"}


def test_multiprotocol_http_step_keeps_legacy_json_shorthand(monkeypatch):
    """既有 {"json": ...} 简写继续可用。"""
    from app.worker.executors import multiprotocol_executor as mp

    captured: dict = {}
    _install_fake_httpx(monkeypatch, captured)

    step = {"url": "https://api.test/legacy", "method": "POST", "json": {"a": "{{v}}"}}
    asyncio.run(mp._execute_http_step(step, {"v": "1"}))

    assert captured["json"] == {"a": "1"}


def test_multiprotocol_http_step_rejects_unsupported_body_type(monkeypatch):
    """不支持的请求体类型必须显式失败，而不是静默丢请求体。"""
    from app.worker.executors import multiprotocol_executor as mp

    captured: dict = {}
    _install_fake_httpx(monkeypatch, captured)

    with pytest.raises(ValueError, match="multipart"):
        asyncio.run(mp._execute_http_step({"url": "https://api.test/x", "body_type": "multipart"}, {}))

    assert captured == {}
