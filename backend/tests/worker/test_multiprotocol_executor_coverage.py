"""multiprotocol_executor 覆盖率补齐：认证分支、请求体形状、WS/gRPC/GraphQL 步骤与 run 分派。

仅新建文件，不改动源码与既有测试；httpx/websockets/grpc/redis 均以 fake 隔离。
"""

import asyncio
import base64
import json

import pytest

from app.models.bootstrap import load_all_models
from app.models.case import RunStatus
from app.worker.executors import multiprotocol_executor as mp

load_all_models()


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
    def __init__(self, config=None):
        self.id = 1
        self.config = config or {}


def _run_case(monkeypatch, steps, *, extra_vars=None, failure_strategy="continue"):
    events = []

    async def _publish(run_id, payload):
        events.append(payload)

    monkeypatch.setattr(mp, "publish_run_event", _publish)
    db, run = _FakeDB(), _FakeRun()
    case = _FakeCase({"steps": steps, "failure_strategy": failure_strategy})
    asyncio.run(mp.run_multiprotocol_case(db, run, case, extra_vars or {}))
    return db, run, events


def test_extract_json_value_edge_inputs():
    assert mp.extract_json_value({"a": 1}, "") is None
    assert mp.extract_json_value("plain", "a") is None
    # 非法 jsonpath 表达式 -> 降级 dot path 且找不到值
    assert mp.extract_json_value({"a": {"b": 2}}, "$[bad") is None
    # dot path 中的空段被跳过
    assert mp.extract_json_value({"a": 1}, "a..") == 1
    assert mp.extract_json_value({"a": [10, 20]}, "a.1") == 20


def test_evaluate_assertion_neq_and_unknown_operator():
    passed, msg = mp.evaluate_assertion({"operator": "neq", "expected": 200}, 500)
    assert passed and msg is None
    passed, msg = mp.evaluate_assertion({"operator": "neq", "expected": 200}, 200)
    assert not passed and "不等于" in (msg or "")
    # 未识别 operator 走兜底比较
    passed, msg = mp.evaluate_assertion({"operator": "gte", "expected": "5"}, "5")
    assert passed and msg is None
    passed, msg = mp.evaluate_assertion({"operator": "gte", "expected": "5"}, "3")
    assert not passed and "断言失败" in (msg or "")


def test_apply_http_auth_supports_basic_apikey_digest_and_oauth2(monkeypatch):
    captured = {}

    def _build_digest(auth_cfg, renderer):
        captured["digest_cfg"] = auth_cfg
        captured["digest_render"] = renderer("{{TOK}}")
        return "DIGEST-AUTH"

    async def _oauth2(auth_cfg, renderer, timeout, extra):
        captured["oauth2"] = (auth_cfg.get("token_url"), renderer("{{TOK}}"), timeout, extra)
        return "Bearer ACC-TOKEN"

    monkeypatch.setattr("app.services.api_auth.build_digest_auth", _build_digest)
    monkeypatch.setattr("app.services.api_auth.resolve_oauth2_client_credentials_token", _oauth2)

    headers = {}
    kwargs = asyncio.run(
        mp._apply_http_auth({"auth": {"type": "basic", "username": "u", "password": "p"}}, headers, {"TOK": "T"})
    )
    assert kwargs == {}
    assert headers["Authorization"] == "Basic " + base64.b64encode(b"u:p").decode()

    headers = {}
    asyncio.run(
        mp._apply_http_auth(
            {"auth": {"type": "apikey", "header": "X-Custom", "value": "{{TOK}}"}}, headers, {"TOK": "T"}
        )
    )
    assert headers == {"X-Custom": "T"}

    headers = {}
    asyncio.run(mp._apply_http_auth({"auth": {"type": "apikey", "header": "", "value": "v"}}, headers, {}))
    assert headers == {}

    headers = {}
    kwargs = asyncio.run(mp._apply_http_auth({"auth": {"type": "digest"}, "timeout": 7}, headers, {"TOK": "T"}))
    assert kwargs == {"auth": "DIGEST-AUTH"}
    assert captured["digest_render"] == "T"

    headers = {}
    kwargs = asyncio.run(
        mp._apply_http_auth(
            {"auth": {"type": "oauth2_client_credentials", "token_url": "https://idp/token"}, "timeout": 3.5},
            headers,
            {"TOK": "T"},
        )
    )
    assert kwargs == {}
    assert headers["Authorization"] == "Bearer ACC-TOKEN"
    assert captured["oauth2"] == ("https://idp/token", "T", 3.5, {})


def test_build_http_request_kwargs_shapes():
    headers, params = {"A": "1"}, {"p": "q"}
    kwargs, body = mp._build_http_request_kwargs({"url": "https://x"}, {}, headers, params)
    assert kwargs == {"headers": headers, "params": params}
    assert body is None

    # 兼容简写 {"json": ...}
    kwargs, body = mp._build_http_request_kwargs({"json": {"k": "{{u}}"}}, {"u": "u3"}, {}, {})
    assert kwargs["json"] == {"k": "u3"}
    assert body == {"k": "u3"}

    kwargs, body = mp._build_http_request_kwargs(
        {"body_type": "form", "body": {"user": "{{u}}"}}, {"u": "u1"}, {"A": "1"}, {}
    )
    assert kwargs["data"] == {"user": "u1"}
    assert body == {"user": "u1"}

    kwargs, body = mp._build_http_request_kwargs({"body_type": "raw", "body": "x={{u}}"}, {"u": "u2"}, {"A": "1"}, {})
    assert kwargs["content"] == "x=u2"
    assert body == "x=u2"

    xml_headers: dict = {}
    kwargs, body = mp._build_http_request_kwargs({"body_type": "xml", "body": "<a/>"}, {}, xml_headers, {})
    assert kwargs["content"] == "<a/>"
    assert xml_headers["Content-Type"] == "application/xml"

    with pytest.raises(ValueError, match="multipart"):
        mp._build_http_request_kwargs({"body_type": "multipart"}, {}, {}, {})

    with pytest.raises(ValueError, match="不支持的请求体类型"):
        mp._build_http_request_kwargs({"body_type": "bogus"}, {}, {}, {})


def test_execute_http_step_falls_back_to_text_body(monkeypatch):
    import httpx

    class _Resp:
        status_code = 200
        headers = {"content-type": "text/plain"}
        text = "raw-body"

        def json(self):
            raise ValueError("not json")

    class _Client:
        def __init__(self, **kwargs):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *exc):
            return False

        async def request(self, method, url, **kwargs):
            return _Resp()

    monkeypatch.setattr(httpx, "AsyncClient", _Client)
    result = asyncio.run(mp._execute_http_step({"url": "https://api.test/x", "method": "get"}, {}))
    assert result["status_code"] == 200
    assert result["body"] == "raw-body"
    assert result["raw_request"]["url"] == "https://api.test/x"


def test_execute_websocket_step_sends_and_receives(monkeypatch):
    import websockets

    class _WS:
        def __init__(self):
            self.sent = []
            self.queue = [json.dumps({"x": 1}), "plain-log"]

        async def send(self, data):
            self.sent.append(data)

        async def recv(self):
            return self.queue.pop(0)

    ws = _WS()

    class _Ctx:
        async def __aenter__(self):
            return ws

        async def __aexit__(self, *exc):
            return False

    monkeypatch.setattr(websockets, "connect", lambda url, open_timeout=None: _Ctx())

    step = {
        "url": "wss://api.test/ws",
        "messages": [
            {"action": "send", "payload": {"k": "{{v}}"}},
            {"action": "receive"},
            {"action": "send", "payload": "raw-ping"},
            {"action": "receive", "timeout": 2},
        ],
    }
    result = asyncio.run(mp._execute_websocket_step(step, {"v": "V1"}))

    assert ws.sent == ['{"k": "V1"}', "raw-ping"]
    assert result["status_code"] == 101
    assert result["messages"] == [{"x": 1}, "plain-log"]
    assert result["body"] == "plain-log"


def test_execute_grpc_step_calls_unary_rpc(monkeypatch):
    import grpc

    class _Channel:
        def __init__(self):
            self.closed = False
            self.path = None

        def unary_unary(self, path, request_serializer=None, response_deserializer=None):
            self.path = path

            async def _call(req):
                assert request_serializer({"a": 1}) == b'{"a": 1}'
                assert request_serializer("text") == b"text"
                assert response_deserializer(b'{"k": 1}') == {"k": 1}
                assert response_deserializer(b"") == {}
                return {"served": req}

            return _call

        async def close(self):
            self.closed = True

    channel = _Channel()
    monkeypatch.setattr(grpc.aio, "insecure_channel", lambda target: channel)

    step = {"target": "127.0.0.1:50051", "service": "s", "method": "m", "body": {"n": "{{v}}"}}
    result = asyncio.run(mp._execute_grpc_step(step, {"v": "5"}))

    assert channel.path == "/s/m"
    assert channel.closed is True
    assert result["status_code"] == 0
    assert result["body"] == {"served": {"n": "5"}}
    assert result["raw_request"]["target"] == "127.0.0.1:50051"


def test_execute_graphql_step_posts_query_and_falls_back_to_text(monkeypatch):
    import httpx

    captured = {}

    class _Resp:
        status_code = 200
        headers = {"content-type": "application/json"}
        text = "not-json"

        def json(self):
            raise ValueError("bad json")

    class _Client:
        def __init__(self, **kwargs):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *exc):
            return False

        async def post(self, url, **kwargs):
            captured["url"] = url
            captured["json"] = kwargs.get("json")
            captured["headers"] = kwargs.get("headers")
            return _Resp()

    monkeypatch.setattr(httpx, "AsyncClient", _Client)
    step = {
        "endpoint": "https://api.test/graphql",
        "query": "query { hero { name } }",
        "variables": {"uid": "{{uid}}"},
        "headers": {"X-T": "1"},
    }
    result = asyncio.run(mp._execute_graphql_step(step, {"uid": "u-1"}))

    assert captured["url"] == "https://api.test/graphql"
    assert captured["json"] == {"query": "query { hero { name } }", "variables": {"uid": "u-1"}}
    assert captured["headers"]["X-T"] == "1"
    assert result["body"] == "not-json"
    assert result["raw_request"]["query"] == "query { hero { name } }"


def test_run_multiprotocol_dispatches_graphql_grpc_and_reports_unknown(monkeypatch):
    async def _graphql(step, context):
        return {"status_code": 200, "body": {"hero": "ok"}, "duration_ms": 3, "raw_request": {"endpoint": "gql"}}

    async def _grpc_step(step, context):
        return {"status_code": 0, "body": {"ok": True}, "duration_ms": 4, "raw_request": {"target": "t"}}

    monkeypatch.setattr(mp, "_execute_graphql_step", _graphql)
    monkeypatch.setattr(mp, "_execute_grpc_step", _grpc_step)

    steps = [
        {
            "name": "gql",
            "protocol": "graphql",
            "assertions": [{"target": "body", "operator": "contains", "expected": "ok"}],
        },
        {"name": "grpc", "protocol": "grpc"},
        {"name": "unknown", "protocol": "smtp"},
    ]
    db, run, events = _run_case(monkeypatch, steps)

    assert run.status == RunStatus.failed
    assert [item.status for item in db.added] == [RunStatus.passed, RunStatus.passed, RunStatus.error]
    assert "未支持的多协议类型" in db.added[2].error_message
    assert db.added[0].response_data.get("assertions")
    assert not db.added[0].error_message
    assert any(event.get("type") == "step_result" and event["step"]["protocol"] == "grpc" for event in events)
    assert events[-1]["type"] == "completed" and events[-1]["status"] == "failed"


def test_run_multiprotocol_stop_strategy_breaks_after_failed_assertion(monkeypatch):
    async def _http(step, context):
        return {"status_code": 200, "body": {"ok": True}, "duration_ms": 1, "raw_request": {}}

    monkeypatch.setattr(mp, "_execute_http_step", _http)
    steps = [
        {
            "name": "fails",
            "protocol": "http",
            "assertions": [{"target": "status_code", "operator": "eq", "expected": 500}],
        },
        {"name": "never", "protocol": "http"},
    ]
    db, run, _events = _run_case(monkeypatch, steps, failure_strategy="stop")

    assert [item.name for item in db.added] == ["fails"]
    assert db.added[0].status == RunStatus.failed
    assert "断言失败" in db.added[0].error_message
    assert run.status == RunStatus.failed


def test_run_multiprotocol_ws_alias_extractions_and_field_assertions(monkeypatch):
    seen_steps = []

    async def _ws(step, context):
        seen_steps.append(step)
        return {
            "status_code": 101,
            "body": {"user": {"id": 7, "name": "u"}},
            "duration_ms": 3,
            "raw_request": {"url": step.get("url")},
        }

    async def _http(step, context):
        seen_steps.append(step)
        return {"status_code": 200, "body": {"ok": True}, "duration_ms": 1, "raw_request": {}}

    monkeypatch.setattr(mp, "_execute_websocket_step", _ws)
    monkeypatch.setattr(mp, "_execute_http_step", _http)

    steps = [
        {
            "name": "ws1",
            "protocol": "ws",
            "url": "wss://api.test/ws",
            "extractions": [
                {"variable": "UID", "expression": "$.user.id"},
                {"variable": "MISS", "expression": "$.nope"},
            ],
            "assertions": [
                {"target": "user.name", "operator": "eq", "expected": "u"},
                {"target": "status_code", "operator": "eq", "expected": 101},
            ],
        },
        {"name": "next", "protocol": "http", "url": "https://api.test/u/{{UID}}"},
    ]
    db, run, events = _run_case(monkeypatch, steps)

    assert run.status == RunStatus.passed
    assert [item.status for item in db.added] == [RunStatus.passed, RunStatus.passed]
    first = db.added[0].response_data
    assert first["protocol"] == "websocket"
    assert first["extractions"][0] == {
        "variable": "UID",
        "type": "jsonpath",
        "expression": "$.user.id",
        "success": True,
        "value": 7,
        "error": None,
    }
    assert first["extractions"][1]["success"] is False
    assert first["extractions"][1]["error"] == "未提取到值"
    assert [item["passed"] for item in first["assertions"]] == [True, True]
    assert first["assertions"][0]["target"] == "user.name"
    assert first["assertions"][0]["actual"] is None and first["assertions"][0]["message"] == ""
    assert seen_steps[0]["url"] == "wss://api.test/ws"
    assert seen_steps[1]["url"] == "https://api.test/u/7"
    assert any(event.get("type") == "step_result" and event["step"]["protocol"] == "websocket" for event in events)
    assert events[-1]["type"] == "completed" and events[-1]["status"] == "passed"


def test_extract_json_value_jsonpath_and_middle_blank_segments():
    assert mp.extract_json_value({"user": {"id": 7}}, "$.user.id") == 7
    assert mp.extract_json_value({"a": {"b": 5}}, "a..b") == 5
    assert mp.extract_json_value({"a": {"b": 5}}, "a..b[") is None
    assert mp.extract_json_value(["x"], "$.0") == "x"


def test_evaluate_assertion_exists_none_and_bearer_auth():
    passed, msg = mp.evaluate_assertion({"operator": "exists"}, None)
    assert passed is False and "字段不存在或为 None" in (msg or "")
    passed, msg = mp.evaluate_assertion({"operator": "exists"}, 0)
    assert passed is True and msg is None

    headers = {}
    kwargs = asyncio.run(mp._apply_http_auth({"auth": {"type": "bearer", "token": "{{TOK}}"}}, headers, {"TOK": "T"}))
    assert kwargs == {} and headers["Authorization"] == "Bearer T"


def test_execute_http_step_forwards_cookies(monkeypatch):
    import httpx

    captured = {}

    class _Resp:
        status_code = 200
        headers = {"content-type": "application/json"}
        text = "{}"

        def json(self):
            return {"ok": True}

    class _Client:
        def __init__(self, **kwargs):
            captured["client_kwargs"] = kwargs

        async def __aenter__(self):
            return self

        async def __aexit__(self, *exc):
            return False

        async def request(self, method, url, **kwargs):
            captured["request_kwargs"] = kwargs
            return _Resp()

    monkeypatch.setattr(httpx, "AsyncClient", _Client)
    step = {"url": "https://api.test/x", "method": "post", "cookies": {"c": "{{v}}"}}
    result = asyncio.run(mp._execute_http_step(step, {"v": "V"}))

    assert captured["request_kwargs"]["cookies"] == {"c": "V"}
    assert result["raw_request"]["cookies"] == {"c": "V"}
    assert result["status_code"] == 200 and result["body"] == {"ok": True}


def test_execute_websocket_step_recv_error_propagates(monkeypatch):
    import websockets

    class _WS:
        async def send(self, data):
            pass

        async def recv(self):
            raise asyncio.TimeoutError("receive timeout")

    class _Ctx:
        async def __aenter__(self):
            return _WS()

        async def __aexit__(self, *exc):
            return False

    monkeypatch.setattr(websockets, "connect", lambda url, open_timeout=None: _Ctx())
    step = {"url": "wss://api.test/ws", "messages": [{"action": "receive", "timeout": 1}]}
    with pytest.raises(asyncio.TimeoutError):
        asyncio.run(mp._execute_websocket_step(step, {}))


def test_execute_websocket_step_skips_unknown_actions(monkeypatch):
    import websockets

    class _WS:
        def __init__(self):
            self.sent = []

        async def send(self, data):
            self.sent.append(data)

        async def recv(self):
            return "never"

    ws = _WS()

    class _Ctx:
        async def __aenter__(self):
            return ws

        async def __aexit__(self, *exc):
            return False

    monkeypatch.setattr(websockets, "connect", lambda url, open_timeout=None: _Ctx())
    step = {"url": "wss://api.test/ws", "messages": [{"action": "wait"}, {"action": "send", "payload": "hi"}]}
    result = asyncio.run(mp._execute_websocket_step(step, {}))
    assert ws.sent == ["hi"]
    assert result["messages"] == [] and result["body"] == {}
