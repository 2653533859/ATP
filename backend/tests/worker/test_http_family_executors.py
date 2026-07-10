"""HTTP 家族执行器（api/graphql/websocket/grpc）的单元缝测试。

按 docs/coverage-baseline-2026-q13.md 的约定：只 fake 传输边界
（httpx.AsyncClient / websockets.connect / grpc channel），执行器自身的
渲染、认证注入、变量提取、断言与落库逻辑全部走真实现。
"""

import asyncio
import json
import sys
import types
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from app.models.bootstrap import load_all_models  # noqa: E402
from app.models.case import RunStatus  # noqa: E402
from app.worker.executors import api_executor, graphql_executor, grpc_executor, websocket_executor  # noqa: E402

load_all_models()


@pytest.fixture()
def healing_recorder(monkeypatch):
    """替换 api_executor 已绑定的 ai_healing 协作函数（不动 sys.modules，避免污染真模块的测试）。"""
    calls = {"diagnosis": [], "run_healing": []}

    async def fake_maybe_enqueue_run_healing(_db, run):
        calls["run_healing"].append(run.id)

    monkeypatch.setattr(api_executor, "apply_healing_hook", lambda _step: False)
    monkeypatch.setattr(api_executor, "enqueue_diagnosis", lambda step_id: calls["diagnosis"].append(step_id))
    monkeypatch.setattr(api_executor, "maybe_enqueue_run_healing", fake_maybe_enqueue_run_healing)
    return calls


class _Obj(types.SimpleNamespace):
    def __getattr__(self, name):
        return None


class _FakeDB:
    def __init__(self):
        self.added = []
        self.commits = 0
        self._next_id = 7000

    def add(self, obj):
        if not getattr(obj, "id", None):
            obj.id = self._next_id
            self._next_id += 1
        self.added.append(obj)

    async def commit(self):
        self.commits += 1

    async def refresh(self, obj):
        return None


def _events_recorder(monkeypatch, module):
    events = []

    async def publish(run_id, payload):
        events.append(payload)

    monkeypatch.setattr(module, "publish_run_event", publish)
    return events


def _run_stub():
    return _Obj(id=1, status=RunStatus.pending)


# ── api_executor ───────────────────────────────────────────


class _FakeResponse:
    def __init__(self, status_code=200, body=None, text="", headers=None):
        self.status_code = status_code
        self._body = body
        self.text = text
        self.headers = headers or {}

    def json(self):
        if self._body is None:
            raise ValueError("not json")
        return self._body


class _FakeAsyncClient:
    """记录请求参数并按脚本返回响应/异常。"""

    script: list = []
    requests: list = []

    def __init__(self, timeout=None):
        self.timeout = timeout

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        return False

    async def request(self, method, url, **kwargs):
        _FakeAsyncClient.requests.append({"method": method, "url": url, **kwargs})
        item = _FakeAsyncClient.script.pop(0)
        if isinstance(item, Exception):
            raise item
        return item

    async def post(self, url, **kwargs):
        return await self.request("POST", url, **kwargs)


@pytest.fixture()
def fake_http(monkeypatch):
    _FakeAsyncClient.script = []
    _FakeAsyncClient.requests = []
    monkeypatch.setattr(api_executor.httpx, "AsyncClient", _FakeAsyncClient)
    monkeypatch.setattr(graphql_executor.httpx, "AsyncClient", _FakeAsyncClient)
    return _FakeAsyncClient


def test_api_executor_extracts_variables_and_injects_auth_across_steps(fake_http, monkeypatch, healing_recorder):
    events = _events_recorder(monkeypatch, api_executor)
    fake_http.script = [
        _FakeResponse(200, {"token": "tok-1"}),
        _FakeResponse(200, {"ok": True}),
    ]
    run = _run_stub()
    case = _Obj(
        config={
            "steps": [
                {
                    "name": "login",
                    "url": "https://api.example.com/login",
                    "method": "POST",
                    "body_type": "json",
                    "body": {"user": "u"},
                    "extractions": [{"variable": "token", "expression": "$.token"}],
                    "assertions": [{"target": "status_code", "operator": "eq", "expected": 200}],
                },
                {
                    "name": "profile",
                    "url": "https://api.example.com/me?t={{token}}",
                    "auth": {"type": "bearer", "token": "{{token}}"},
                    "assertions": [
                        {"target": "body", "operator": "exists", "expression": "$.ok"},
                        {"target": "duration", "operator": "lt", "expected": 60_000},
                    ],
                },
            ]
        }
    )
    db = _FakeDB()

    asyncio.run(api_executor.run_api_case(db, run, case, {}))

    assert run.status is RunStatus.passed
    assert fake_http.requests[0]["json"] == {"user": "u"}
    second = fake_http.requests[1]
    assert second["url"].endswith("t=tok-1")
    assert second["headers"]["Authorization"] == "Bearer tok-1"
    assert [e["type"] for e in events] == ["step_result", "step_result", "completed"]
    assert healing_recorder["run_healing"] == [1]
    assert all(step.status is RunStatus.passed for step in db.added)


def test_api_executor_marks_step_failed_on_assertion_and_stops_assertions(fake_http, monkeypatch, healing_recorder):
    _events_recorder(monkeypatch, api_executor)
    fake_http.script = [_FakeResponse(500, {"detail": "boom"})]
    run = _run_stub()
    case = _Obj(
        config={
            "steps": [
                {
                    "url": "https://api.example.com/x",
                    "assertions": [{"target": "status_code", "operator": "eq", "expected": 200}],
                }
            ]
        }
    )
    db = _FakeDB()

    asyncio.run(api_executor.run_api_case(db, run, case, {}))

    assert run.status is RunStatus.failed
    assert db.added[0].status is RunStatus.failed
    assert "断言失败" in db.added[0].error_message


def test_api_executor_marks_step_error_when_transport_raises(fake_http, monkeypatch, healing_recorder):
    _events_recorder(monkeypatch, api_executor)
    fake_http.script = [RuntimeError("connect refused")]
    run = _run_stub()
    case = _Obj(config={"steps": [{"url": "https://api.example.com/x"}]})
    db = _FakeDB()

    asyncio.run(api_executor.run_api_case(db, run, case, {}))

    assert run.status is RunStatus.failed
    assert db.added[0].status is RunStatus.error
    assert "connect refused" in db.added[0].error_message


def test_api_executor_enqueues_diagnosis_when_healing_hook_requests_it(fake_http, monkeypatch, healing_recorder):
    _events_recorder(monkeypatch, api_executor)
    monkeypatch.setattr(api_executor, "apply_healing_hook", lambda _step: True)
    fake_http.script = [_FakeResponse(200, {"ok": True})]
    db = _FakeDB()

    asyncio.run(api_executor.run_api_case(db, _run_stub(), _Obj(config={"steps": [{"url": "https://x"}]}), {}))

    assert healing_recorder["diagnosis"] == [db.added[0].id]


def test_api_executor_falls_back_to_single_step_config_and_basic_auth(fake_http, monkeypatch, healing_recorder):
    _events_recorder(monkeypatch, api_executor)
    fake_http.script = [_FakeResponse(200, None, text="plain")]
    run = _run_stub()
    # 无 steps 键：整个 config 即单步；basic 认证；form 提交
    case = _Obj(
        config={
            "url": "https://api.example.com/form",
            "method": "post",
            "body_type": "form",
            "body": {"a": "1"},
            "auth": {"type": "basic", "username": "u", "password": "p"},
        }
    )

    asyncio.run(api_executor.run_api_case(_FakeDB(), run, case, {}))

    request = fake_http.requests[0]
    assert request["method"] == "POST"
    assert request["data"] == {"a": "1"}
    assert request["headers"]["Authorization"].startswith("Basic ")
    assert run.status is RunStatus.passed  # 无断言即视为通过


@pytest.mark.parametrize(
    ("assertion", "expected_ok"),
    [
        ({"target": "status_code", "operator": "eq", "expected": 200}, True),
        ({"target": "body", "operator": "contains", "expected": "tok", "expression": "$.token"}, True),
        ({"target": "body", "operator": "eq", "expected": "x", "expression": "$.missing"}, False),
        ({"target": "header", "operator": "exists", "expression": "x-req-id"}, True),
        ({"target": "duration", "operator": "gt", "expected": 5}, True),
        ({"target": "duration", "operator": "lt", "expected": 5}, False),
        ({"target": "status_code", "operator": "unknown", "expected": 1}, False),
    ],
)
def test_api_assert_operator_matrix(assertion, expected_ok):
    resp = _FakeResponse(200, {"token": "tok-1"}, headers={"x-req-id": "r1"})

    ok, message = api_executor._assert(assertion, resp, {"token": "tok-1"}, duration_ms=10)

    assert ok is expected_ok
    if not expected_ok:
        assert message


def test_api_render_and_jsonpath_edges():
    assert api_executor._render("{{a}}-{{b}}", {"a": 1, "b": "x"}) == "1-x"
    assert api_executor._jsonpath_extract({"a": [1, 2]}, "$.a[1]") == 2
    assert api_executor._jsonpath_extract({}, "$.missing") is None
    assert api_executor._jsonpath_extract({}, "((bad") is None


# ── graphql_executor ───────────────────────────────────────


def test_graphql_executor_builds_request_and_extracts_variables(fake_http, monkeypatch):
    events = _events_recorder(monkeypatch, graphql_executor)
    fake_http.script = [
        _FakeResponse(200, {"data": {"login": {"token": "gq-tok"}}}),
        _FakeResponse(200, {"data": {"me": {"name": "amy"}}}),
    ]
    run = _run_stub()
    case = _Obj(
        config={
            "steps": [
                {
                    "endpoint": "https://gql.example.com",
                    "query": "mutation Login { login { token } }",
                    "operation_name": "Login",
                    "variables": {"user": "{{user}}", "keep": 7},
                    "extractions": [{"variable": "token", "expression": "$.data.login.token"}],
                },
                {
                    "endpoint": "https://gql.example.com",
                    "query": "query Me { me { name } }",
                    "auth": {"type": "apikey", "header": "X-Token", "value": "{{token}}"},
                    "assertions": [
                        {"target": "body", "operator": "eq", "expected": "amy", "expression": "$.data.me.name"}
                    ],
                },
            ]
        }
    )

    asyncio.run(graphql_executor.run_graphql_case(_FakeDB(), run, case, {"user": "amy"}))

    assert run.status is RunStatus.passed
    first = fake_http.requests[0]
    assert first["json"] == {
        "query": "mutation Login { login { token } }",
        "variables": {"user": "amy", "keep": 7},
        "operationName": "Login",
    }
    assert fake_http.requests[1]["headers"]["X-Token"] == "gq-tok"
    assert events[-1]["type"] == "completed" and events[-1]["status"] == "passed"


def test_graphql_executor_records_transport_error(fake_http, monkeypatch):
    _events_recorder(monkeypatch, graphql_executor)
    fake_http.script = [RuntimeError("dns fail")]
    run = _run_stub()
    db = _FakeDB()

    asyncio.run(
        graphql_executor.run_graphql_case(
            db, run, _Obj(config={"steps": [{"endpoint": "https://gql", "query": "{ ping }"}]}), {}
        )
    )

    assert run.status is RunStatus.failed
    assert db.added[0].status is RunStatus.error
    assert "dns fail" in db.added[0].error_message


def test_graphql_executor_bearer_and_basic_auth_and_assertion_failure(fake_http, monkeypatch):
    _events_recorder(monkeypatch, graphql_executor)
    fake_http.script = [
        _FakeResponse(200, {"data": {"ok": True}}),
        _FakeResponse(200, {"errors": [{"message": "denied"}]}),
    ]
    run = _run_stub()
    case = _Obj(
        config={
            "steps": [
                {
                    "endpoint": "https://gql",
                    "query": "{ ping }",
                    "auth": {"type": "bearer", "token": "tok-9"},
                },
                {
                    "endpoint": "https://gql",
                    "query": "{ pong }",
                    "auth": {"type": "basic", "username": "u", "password": "p"},
                    "assertions": [
                        {"target": "body", "operator": "not_exists", "expression": "$.errors"},
                    ],
                },
            ]
        }
    )
    db = _FakeDB()

    asyncio.run(graphql_executor.run_graphql_case(db, run, case, {}))

    assert fake_http.requests[0]["headers"]["Authorization"] == "Bearer tok-9"
    assert fake_http.requests[1]["headers"]["Authorization"].startswith("Basic ")
    assert run.status is RunStatus.failed
    assert db.added[1].status is RunStatus.failed
    assert "断言失败" in db.added[1].error_message


@pytest.mark.parametrize(
    ("assertion", "expected_ok"),
    [
        ({"target": "status_code", "operator": "eq", "expected": 200}, True),
        ({"target": "body", "operator": "contains", "expected": "pong", "expression": "$.data.echo"}, True),
        ({"target": "header", "operator": "exists", "expression": "x-trace"}, True),
        ({"target": "duration", "operator": "gt", "expected": 1}, True),
        ({"target": "body", "operator": "nope"}, False),
    ],
)
def test_graphql_assert_matrix(assertion, expected_ok):
    resp = _FakeResponse(200, {"data": {"echo": "pong"}}, headers={"x-trace": "t"})

    ok, _message = graphql_executor._assert(assertion, resp, {"data": {"echo": "pong"}}, duration_ms=10)

    assert ok is expected_ok


def test_graphql_render_and_jsonpath_edges():
    assert graphql_executor._render("{{a}}", {"a": "v"}) == "v"
    assert graphql_executor._jsonpath_extract({"a": {"b": 3}}, "$.a.b") == 3
    assert graphql_executor._jsonpath_extract({}, "((bad") is None


# ── websocket_executor ─────────────────────────────────────


class _FakeWS:
    def __init__(self, incoming):
        self.incoming = list(incoming)
        self.sent = []

    async def send(self, data):
        self.sent.append(data)

    async def recv(self):
        if not self.incoming:
            await asyncio.sleep(3600)
        return self.incoming.pop(0)


class _FakeConnect:
    last = None

    def __init__(self, url, additional_headers=None, open_timeout=None, close_timeout=None, incoming=()):
        self.url = url
        self.additional_headers = additional_headers
        self.ws = _FakeWS(incoming)
        _FakeConnect.last = self

    async def __aenter__(self):
        return self.ws

    async def __aexit__(self, *args):
        return False


def _install_ws(monkeypatch, incoming):
    def connect(url, additional_headers=None, open_timeout=None, close_timeout=None):
        return _FakeConnect(url, additional_headers=additional_headers, open_timeout=open_timeout, incoming=incoming)

    monkeypatch.setattr(websocket_executor.websockets, "connect", connect)


def test_websocket_executor_send_receive_extract_assert_and_disconnect(monkeypatch):
    events = _events_recorder(monkeypatch, websocket_executor)
    _install_ws(monkeypatch, incoming=[json.dumps({"type": "welcome", "session": "s-9"})])
    run = _run_stub()
    case = _Obj(
        config={
            "steps": [
                {
                    "url": "wss://ws.example.com/{{room}}",
                    "headers": {"X-Room": "{{room}}"},
                    "messages": [
                        {"action": "send", "data": '{"hello": "{{room}}"}', "data_type": "json"},
                        {
                            "action": "receive",
                            "extractions": [{"variable": "session", "expression": "$.session"}],
                            "assertions": [
                                {"target": "body", "operator": "eq", "expected": "welcome", "expression": "$.type"}
                            ],
                        },
                        {"action": "disconnect"},
                    ],
                }
            ]
        }
    )
    db = _FakeDB()

    asyncio.run(websocket_executor.run_websocket_case(db, run, case, {"room": "r1"}))

    assert run.status is RunStatus.passed
    conn = _FakeConnect.last
    assert conn.url == "wss://ws.example.com/r1"
    assert conn.additional_headers == {"X-Room": "r1"}
    assert conn.ws.sent == ['{"hello": "r1"}']
    step = db.added[0]
    actions = [m["action"] for m in step.response_data["messages"]]
    assert actions == ["send", "receive", "disconnect"]
    assert events[-1]["status"] == "passed"


def test_websocket_executor_marks_receive_timeout_as_failure(monkeypatch):
    _events_recorder(monkeypatch, websocket_executor)
    _install_ws(monkeypatch, incoming=[])  # 永不来消息
    run = _run_stub()
    case = _Obj(config={"steps": [{"url": "wss://ws", "messages": [{"action": "receive", "timeout": 0.01}]}]})
    db = _FakeDB()

    asyncio.run(websocket_executor.run_websocket_case(db, run, case, {}))

    assert run.status is RunStatus.failed
    assert "接收超时" in db.added[0].error_message


def test_websocket_executor_records_connection_error(monkeypatch):
    _events_recorder(monkeypatch, websocket_executor)

    def broken_connect(*args, **kwargs):
        raise RuntimeError("handshake rejected")

    monkeypatch.setattr(websocket_executor.websockets, "connect", broken_connect)
    run = _run_stub()
    db = _FakeDB()

    asyncio.run(websocket_executor.run_websocket_case(db, run, _Obj(config={"steps": [{"url": "wss://ws"}]}), {}))

    assert run.status is RunStatus.failed
    assert db.added[0].status is RunStatus.error
    assert "handshake rejected" in db.added[0].error_message


@pytest.mark.parametrize(
    ("assertion", "expected_ok"),
    [
        ({"target": "body", "operator": "eq", "expected": "1", "expression": "$.a"}, True),
        ({"target": "raw", "operator": "contains", "expected": '"a"'}, True),
        ({"target": "body", "operator": "not_exists", "expression": "$.missing"}, True),
        ({"target": "body", "operator": "unknown"}, False),
    ],
)
def test_websocket_assert_matrix(assertion, expected_ok):
    ok, _message = websocket_executor._assert_ws(assertion, {"a": 1})

    assert ok is expected_ok


def test_websocket_executor_injects_auth_and_keeps_non_json_payloads(monkeypatch):
    _events_recorder(monkeypatch, websocket_executor)
    _install_ws(monkeypatch, incoming=["plain-text-pong"])
    run = _run_stub()
    case = _Obj(
        config={
            "steps": [
                {
                    "url": "wss://ws",
                    "auth": {"type": "apikey", "header": "X-Key", "value": "k-1"},
                    "messages": [
                        # data_type=json 但内容非法 JSON：按原文发送，不报错
                        {"action": "send", "data": "not json", "data_type": "json"},
                        {
                            "action": "receive",
                            "assertions": [{"target": "raw", "operator": "contains", "expected": "pong"}],
                        },
                    ],
                }
            ]
        }
    )
    db = _FakeDB()

    asyncio.run(websocket_executor.run_websocket_case(db, run, case, {}))

    conn = _FakeConnect.last
    assert conn.additional_headers == {"X-Key": "k-1"}
    assert conn.ws.sent == ["not json"]
    assert run.status is RunStatus.passed


def test_websocket_executor_bearer_and_basic_auth_headers(monkeypatch):
    _events_recorder(monkeypatch, websocket_executor)
    _install_ws(monkeypatch, incoming=[])
    case = _Obj(
        config={
            "steps": [
                {"url": "wss://a", "auth": {"type": "bearer", "token": "t-1"}, "messages": []},
                {"url": "wss://b", "auth": {"type": "basic", "username": "u", "password": "p"}, "messages": []},
            ]
        }
    )

    asyncio.run(websocket_executor.run_websocket_case(_FakeDB(), _run_stub(), case, {}))

    assert _FakeConnect.last.additional_headers["Authorization"].startswith("Basic ")


def test_websocket_render_and_jsonpath_edges():
    assert websocket_executor._render("{{x}}", {"x": 9}) == "9"
    assert websocket_executor._jsonpath_extract({"a": 1}, "$.a") == 1
    assert websocket_executor._jsonpath_extract({}, "((bad") is None


# ── grpc_executor ──────────────────────────────────────────

_ECHO_PROTO = """
syntax = "proto3";
package demo;
message EchoRequest { string text = 1; }
message EchoReply { string text = 1; }
service Echo { rpc Say (EchoRequest) returns (EchoReply); }
"""


def test_grpc_compile_proto_rejects_bad_syntax():
    with pytest.raises(RuntimeError, match="Proto 编译失败"):
        grpc_executor._compile_proto("syntax = broken")


class _FakeChannel:
    def __init__(self, responder):
        self.responder = responder
        self.closed = False
        self.calls = []

    def unary_unary(self, method_path, request_serializer=None, response_deserializer=None):
        async def call(request_msg, timeout=None, metadata=None):
            self.calls.append({"path": method_path, "request": request_msg, "metadata": metadata})
            return self.responder(request_msg)

        return call

    async def close(self):
        self.closed = True


def _install_grpc_channel(monkeypatch, responder):
    channel = _FakeChannel(responder)
    monkeypatch.setattr(grpc_executor.grpc.aio, "insecure_channel", lambda target: channel)
    return channel


def _grpc_case(assertions=None, request_json='{"text": "{{word}}"}'):
    return _Obj(
        config={
            "steps": [
                {
                    "target": "localhost:50051",
                    "proto_content": _ECHO_PROTO,
                    "service": "demo.Echo",
                    "method": "Say",
                    "request_json": request_json,
                    "metadata": {"x-tenant": "{{word}}"},
                    "assertions": assertions or [],
                }
            ]
        }
    )


def test_grpc_executor_compiles_proto_and_asserts_response(monkeypatch):
    events = _events_recorder(monkeypatch, grpc_executor)

    def responder(request_msg):
        assert request_msg.text == "hello"
        # 从请求消息的 DESCRIPTOR 池里找回复类型
        pool_file = request_msg.DESCRIPTOR.file.pool
        from google.protobuf import message_factory

        RespClass = message_factory.GetMessageClass(pool_file.FindMessageTypeByName("demo.EchoReply"))
        return RespClass(text="world")

    channel = _install_grpc_channel(monkeypatch, responder)
    run = _run_stub()
    case = _grpc_case(
        assertions=[
            {"target": "body", "operator": "eq", "expected": "world", "expression": "$.text"},
            {"target": "grpc_status", "operator": "eq", "expected": "OK"},
        ]
    )
    db = _FakeDB()

    asyncio.run(grpc_executor.run_grpc_case(db, run, case, {"word": "hello"}))

    assert run.status is RunStatus.passed
    assert channel.closed is True
    assert channel.calls[0]["path"] == "/demo.Echo/Say"
    assert channel.calls[0]["metadata"] == [("x-tenant", "hello")]
    assert events[-1]["status"] == "passed"


def test_grpc_executor_treats_rpc_error_with_matching_assertion_as_pass(monkeypatch):
    _events_recorder(monkeypatch, grpc_executor)
    import grpc as grpc_lib

    def responder(_request_msg):
        raise grpc_lib.aio.AioRpcError(
            grpc_lib.StatusCode.UNAVAILABLE,
            grpc_lib.aio.Metadata(),
            grpc_lib.aio.Metadata(),
            details="backend down",
        )

    _install_grpc_channel(monkeypatch, responder)
    run = _run_stub()
    case = _grpc_case(assertions=[{"target": "grpc_status", "operator": "eq", "expected": "UNAVAILABLE"}])
    db = _FakeDB()

    asyncio.run(grpc_executor.run_grpc_case(db, run, case, {"word": "hello"}))

    assert run.status is RunStatus.passed
    assert db.added[0].response_data["grpc_status"] == "UNAVAILABLE"


def test_grpc_executor_marks_unasserted_rpc_error_as_error(monkeypatch):
    _events_recorder(monkeypatch, grpc_executor)
    import grpc as grpc_lib

    def responder(_request_msg):
        raise grpc_lib.aio.AioRpcError(
            grpc_lib.StatusCode.DEADLINE_EXCEEDED,
            grpc_lib.aio.Metadata(),
            grpc_lib.aio.Metadata(),
            details="too slow",
        )

    _install_grpc_channel(monkeypatch, responder)
    run = _run_stub()
    db = _FakeDB()

    asyncio.run(grpc_executor.run_grpc_case(db, run, _grpc_case(), {"word": "hello"}))

    assert run.status is RunStatus.failed
    assert db.added[0].status is RunStatus.error
    assert "DEADLINE_EXCEEDED" in db.added[0].error_message


def test_grpc_executor_rejects_invalid_request_json(monkeypatch):
    _events_recorder(monkeypatch, grpc_executor)
    _install_grpc_channel(monkeypatch, lambda _m: None)
    run = _run_stub()
    db = _FakeDB()

    asyncio.run(grpc_executor.run_grpc_case(db, run, _grpc_case(request_json="{broken"), {"word": "x"}))

    assert db.added[0].status is RunStatus.error
    assert "Request JSON 解析失败" in db.added[0].error_message


@pytest.mark.parametrize(
    ("assertion", "expected_ok"),
    [
        ({"target": "grpc_status", "operator": "eq", "expected": "OK"}, True),
        ({"target": "duration", "operator": "lt", "expected": 10_000}, True),
        ({"target": "body", "operator": "not_exists", "expression": "$.x"}, True),
        ({"target": "body", "operator": "nope"}, False),
    ],
)
def test_grpc_assert_matrix(assertion, expected_ok):
    ok, _message = grpc_executor._assert_grpc(assertion, {"a": 1}, "OK", 25)

    assert ok is expected_ok


def test_grpc_executor_uses_tls_channel_when_configured(monkeypatch):
    _events_recorder(monkeypatch, grpc_executor)
    import grpc as grpc_lib

    channel = _FakeChannel(lambda _m: None)
    secure_calls = []

    def fake_secure_channel(target, creds):
        secure_calls.append(target)
        return channel

    monkeypatch.setattr(grpc_executor.grpc, "ssl_channel_credentials", lambda: "creds", raising=False)
    monkeypatch.setattr(grpc_executor.grpc.aio, "secure_channel", fake_secure_channel)
    case = _grpc_case()
    case.config["steps"][0]["use_tls"] = True
    case.config["steps"][0]["request_json"] = "{broken"  # 走到 channel 创建前的错误即可，不实际调用

    asyncio.run(grpc_executor.run_grpc_case(_FakeDB(), _run_stub(), case, {"word": "x"}))

    # request_json 在 channel 创建之前失败，TLS 分支不应被触达；改用合法 JSON 再驱动一次
    case2 = _grpc_case(assertions=[{"target": "grpc_status", "operator": "eq", "expected": "OK"}])
    case2.config["steps"][0]["use_tls"] = True

    def responder(request_msg):
        from google.protobuf import message_factory

        pool = request_msg.DESCRIPTOR.file.pool
        RespClass = message_factory.GetMessageClass(pool.FindMessageTypeByName("demo.EchoReply"))
        return RespClass(text="ok")

    channel.responder = responder
    run = _run_stub()
    asyncio.run(grpc_executor.run_grpc_case(_FakeDB(), run, case2, {"word": "x"}))

    assert secure_calls[-1] == "localhost:50051"
    assert run.status is RunStatus.passed


@pytest.mark.parametrize("module", [api_executor, graphql_executor, websocket_executor, grpc_executor])
def test_executor_safe_publish_swallows_redis_failures(monkeypatch, module):
    async def broken_publish(_run_id, _payload):
        raise RuntimeError("redis down")

    monkeypatch.setattr(module, "publish_run_event", broken_publish)
    asyncio.run(module._safe_publish_run_event(1, {"type": "step_result"}))
