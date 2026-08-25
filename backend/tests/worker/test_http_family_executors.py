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

import httpx
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
    def __init__(self, status_code=200, body=None, text="", headers=None, sse_lines=()):
        self.status_code = status_code
        self._body = body
        self.text = text
        self.headers = headers or {}
        self.sse_lines = list(sse_lines)

    def json(self):
        if self._body is None:
            raise ValueError("not json")
        return self._body

    async def aiter_lines(self):
        for line in self.sse_lines:
            yield line


class _FakeStreamContext:
    def __init__(self, client, method, url, kwargs):
        self.client = client
        self.method = method
        self.url = url
        self.kwargs = kwargs
        self.response = None

    async def __aenter__(self):
        self.response = await self.client.request(self.method, self.url, **self.kwargs)
        return self.response

    async def __aexit__(self, *args):
        return False


class _FakeAsyncClient:
    """记录请求参数并按脚本返回响应/异常。"""

    script: list = []
    requests: list = []

    def __init__(self, timeout=None):
        self.timeout = timeout
        self.cookies = httpx.Cookies()

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        return False

    async def aclose(self):
        return None

    async def request(self, method, url, **kwargs):
        _FakeAsyncClient.requests.append(
            {
                "method": method,
                "url": url,
                "cookie_snapshot": {cookie.name: cookie.value for cookie in self.cookies.jar},
                **kwargs,
            }
        )
        item = _FakeAsyncClient.script.pop(0)
        if isinstance(item, Exception):
            raise item
        return item

    async def post(self, url, **kwargs):
        return await self.request("POST", url, **kwargs)

    def stream(self, method, url, **kwargs):
        return _FakeStreamContext(self, method, url, kwargs)


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


def test_api_executor_redacts_dataset_fields_from_persisted_evidence(fake_http, monkeypatch, healing_recorder):
    events = _events_recorder(monkeypatch, api_executor)
    fake_http.script = [_FakeResponse(200, {"token": "response-secret"})]
    case = _Obj(
        config={
            "dataset_redact_fields": ["token", "user.password"],
            "steps": [
                {
                    "url": "https://api.example.com/login",
                    "method": "POST",
                    "body_type": "json",
                    "body": {"token": "request-secret", "user": {"password": "request-password"}},
                }
            ],
        }
    )
    db = _FakeDB()

    asyncio.run(api_executor.run_api_case(db, _run_stub(), case, {}))

    step = db.added[0]
    assert fake_http.requests[0]["json"] == {
        "token": "request-secret",
        "user": {"password": "request-password"},
    }
    assert step.request_data["body"] == {"token": "***", "user": {"password": "***"}}
    assert step.response_data["body"]["token"] == "***"
    assert events[0]["step"]["request_data"] == step.request_data
    assert events[0]["step"]["response_data"] == step.response_data


def test_api_executor_applies_stop_failure_strategy_and_records_skipped_step(fake_http, monkeypatch, healing_recorder):
    _events_recorder(monkeypatch, api_executor)
    fake_http.script = [_FakeResponse(500, {"error": "boom"})]
    run = _run_stub()
    case = _Obj(
        config={
            "failure_strategy": "stop",
            "steps": [
                {
                    "name": "login",
                    "url": "https://api.example.com/login",
                    "assertions": [{"target": "status_code", "operator": "eq", "expected": 200}],
                },
                {"name": "profile", "url": "https://api.example.com/me"},
            ],
        }
    )
    db = _FakeDB()

    asyncio.run(api_executor.run_api_case(db, run, case, {}))

    assert run.status is RunStatus.failed
    assert len(fake_http.requests) == 1
    assert [step.status for step in db.added] == [RunStatus.failed, RunStatus.skipped]
    assert "停止" in db.added[-1].error_message


def test_api_executor_skips_only_explicit_dependents(fake_http, monkeypatch, healing_recorder):
    _events_recorder(monkeypatch, api_executor)
    fake_http.script = [_FakeResponse(500, {"error": "boom"}), _FakeResponse(200, {"ok": True})]
    run = _run_stub()
    case = _Obj(
        config={
            "failure_strategy": "continue",
            "steps": [
                {
                    "name": "login",
                    "url": "https://api.example.com/login",
                    "assertions": [{"target": "status_code", "operator": "eq", "expected": 200}],
                },
                {"name": "profile", "url": "https://api.example.com/me", "depends_on": [0]},
                {"name": "health", "url": "https://api.example.com/health"},
            ],
        }
    )
    db = _FakeDB()

    asyncio.run(api_executor.run_api_case(db, run, case, {}))

    assert len(fake_http.requests) == 2
    assert [step.status for step in db.added] == [RunStatus.failed, RunStatus.skipped, RunStatus.passed]
    assert "依赖步骤" in db.added[1].error_message


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


def test_api_executor_oauth2_client_credentials_fetches_and_reuses_token(fake_http, monkeypatch, healing_recorder):
    _events_recorder(monkeypatch, api_executor)
    fake_http.script = [
        _FakeResponse(200, {"access_token": "oauth-token"}),
        _FakeResponse(200, {"ok": True}),
        _FakeResponse(200, {"ok": True}),
    ]
    auth = {
        "type": "oauth2_client_credentials",
        "token_url": "https://issuer.example.com/oauth/token",
        "client_id": "client-1",
        "client_secret": "secret-1",
        "scope": "read",
    }
    case = _Obj(
        config={
            "steps": [
                {"url": "https://api.example.com/one", "auth": auth},
                {"url": "https://api.example.com/two", "auth": auth},
            ]
        }
    )

    asyncio.run(api_executor.run_api_case(_FakeDB(), _run_stub(), case, {}))

    assert len(fake_http.requests) == 3
    token_request, first_api_request, second_api_request = fake_http.requests
    assert token_request["url"] == auth["token_url"]
    assert token_request["auth"] == ("client-1", "secret-1")
    assert token_request["data"] == {"grant_type": "client_credentials", "scope": "read"}
    assert first_api_request["headers"]["Authorization"] == "Bearer oauth-token"
    assert second_api_request["headers"]["Authorization"] == "Bearer oauth-token"


def test_api_executor_digest_auth_is_passed_to_httpx(fake_http, monkeypatch, healing_recorder):
    _events_recorder(monkeypatch, api_executor)
    marker = object()
    monkeypatch.setattr(api_executor, "build_digest_auth", lambda *_args: marker)
    fake_http.script = [_FakeResponse(200, {"ok": True})]
    case = _Obj(
        config={
            "steps": [
                {
                    "url": "https://api.example.com/protected",
                    "auth": {"type": "digest", "username": "u", "password": "p"},
                }
            ]
        }
    )

    asyncio.run(api_executor.run_api_case(_FakeDB(), _run_stub(), case, {}))

    assert fake_http.requests[0]["auth"] is marker


def test_api_executor_reuses_project_cookie_session_when_enabled(fake_http, monkeypatch, healing_recorder):
    _events_recorder(monkeypatch, api_executor)
    loaded = [{"name": "session", "value": "sid-1", "domain": "api.example.com", "path": "/"}]
    saved = []

    async def load_session(project_id):
        assert project_id == 1
        return loaded

    async def save_session(project_id, cookies):
        saved.append((project_id, cookies))

    monkeypatch.setattr(api_executor, "load_project_api_session", load_session)
    monkeypatch.setattr(api_executor, "save_project_api_session", save_session)
    fake_http.script = [_FakeResponse(200, {"ok": True}), _FakeResponse(200, {"ok": True})]
    case = _Obj(
        project_id=1,
        config={
            "reuse_api_session": True,
            "steps": [
                {"url": "https://api.example.com/me"},
                {"url": "https://api.example.com/orders"},
            ],
        },
    )

    asyncio.run(api_executor.run_api_case(_FakeDB(), _run_stub(), case, {}))

    assert fake_http.requests[0]["cookie_snapshot"] == {"session": "sid-1"}
    assert fake_http.requests[1]["cookie_snapshot"] == {"session": "sid-1"}
    assert saved[0][0] == 1
    assert saved[0][1][0]["name"] == "session"


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


def test_api_restricted_expression_assertions_allow_data_only_access():
    resp = _FakeResponse(201, {"user": {"id": 7}}, headers={"content-type": "application/json"})
    ok, message = api_executor._assert(
        {"target": "expression", "expression": "status_code == 201 and body.user.id == 7 and response_time_ms < 100"},
        resp,
        {"user": {"id": 7}},
        duration_ms=10,
    )
    assert ok is True and message == ""
    ok, message = api_executor._assert(
        {"operator": "expression", "expression": "__import__('os').getcwd()"},
        resp,
        {"user": {"id": 7}},
        duration_ms=10,
    )
    assert ok is False and ("不允许" in message or "无效" in message)


def test_api_render_and_jsonpath_edges():
    assert api_executor._render("{{a}}-{{b}}", {"a": 1, "b": "x"}) == "1-x"
    assert api_executor._jsonpath_extract({"a": [1, 2]}, "$.a[1]") == 2
    assert api_executor._jsonpath_extract({}, "$.missing") is None
    assert api_executor._jsonpath_extract({}, "((bad") is None


def test_api_executor_supports_cookies_multipart_and_xml(fake_http, monkeypatch, healing_recorder):
    _events_recorder(monkeypatch, api_executor)
    monkeypatch.setattr(api_executor, "read_bytes", lambda object_name: b"file-content")
    fake_http.script = [_FakeResponse(200, None, text="<root><id>u-1</id></root>")]
    run = _run_stub()
    case = _Obj(
        config={
            "steps": [
                {
                    "url": "https://api.example.com/upload/{{id}}",
                    "method": "POST",
                    "cookies": {"session": "{{session}}"},
                    "body_type": "multipart",
                    "multipart": [
                        {"name": "title", "type": "text", "value": "hello"},
                        {
                            "name": "attachment",
                            "type": "file",
                            "filename": "a.txt",
                            "object_name": "api-files/projects/1/a.txt",
                            "content_type": "text/plain",
                        },
                    ],
                    "extractions": [{"variable": "user_id", "type": "xpath", "expression": "//id"}],
                }
            ]
        }
    )

    db = _FakeDB()
    asyncio.run(api_executor.run_api_case(db, run, case, {"id": "u-1", "session": "sid"}))

    request = fake_http.requests[0]
    assert request["cookies"] == {"session": "sid"}
    assert request["data"] == {"title": "hello"}
    assert request["files"][0][0] == "attachment"
    assert request["files"][0][1][0:2] == ("a.txt", b"file-content")
    assert db.added[0].request_data["body"][1]["object_name"] == "api-files/projects/1/a.txt"
    assert run.status is RunStatus.passed


def test_api_xpath_and_json_schema_assertions():
    xml_response = _FakeResponse(200, None, text="<root><user id='u-1'><name>Amy</name></user></root>")
    assert api_executor._xpath_extract(xml_response.text, "//user/name") == "Amy"
    assert api_executor._xpath_extract(xml_response.text, "//user/@id") == "u-1"

    schema = {"type": "object", "required": ["id"], "properties": {"id": {"type": "integer"}}}
    ok, message = api_executor._assert(
        {"target": "json_schema", "operator": "valid", "expected": schema},
        _FakeResponse(200, {"id": 1}),
        {"id": 1},
        3,
    )
    assert ok is True and message == ""

    ok, message = api_executor._assert(
        {"target": "json_schema", "operator": "valid", "expected": schema},
        _FakeResponse(200, {"id": "wrong"}),
        {"id": "wrong"},
        3,
    )
    assert ok is False
    assert "JSON Schema" in message


def test_api_executor_consumes_sse_events_and_applies_assertions(fake_http, monkeypatch, healing_recorder):
    _events_recorder(monkeypatch, api_executor)
    fake_http.script = [
        _FakeResponse(
            200,
            None,
            headers={"content-type": "text/event-stream"},
            sse_lines=["event: ready", 'data: {"ok":true}', "", "data: done", ""],
        )
    ]
    run = _run_stub()
    case = _Obj(
        config={
            "steps": [
                {
                    "url": "https://api.example.com/events",
                    "response_type": "sse",
                    "sse_max_events": 2,
                    "assertions": [
                        {"target": "body", "operator": "contains", "expected": "done", "expression": "$[1].data"}
                    ],
                }
            ]
        }
    )

    asyncio.run(api_executor.run_api_case(_FakeDB(), run, case, {}))

    assert run.status is RunStatus.passed
    assert fake_http.requests[0]["url"] == "https://api.example.com/events"


def test_api_executor_runs_safe_pre_and_post_actions(fake_http, monkeypatch, healing_recorder):
    _events_recorder(monkeypatch, api_executor)
    fake_http.script = [_FakeResponse(200, {"token": "tok-2"}), _FakeResponse(200, {"ok": True})]
    case = _Obj(
        config={
            "steps": [
                {
                    "name": "prepare",
                    "url": "https://api.example.com/users/{{request_id}}",
                    "pre_actions": [{"action": "set_variable", "variable": "request_id", "value": "u-2"}],
                    "post_actions": [{"action": "extract", "variable": "token", "expression": "$.token"}],
                },
                {
                    "name": "call",
                    "url": "https://api.example.com/me",
                    "headers": {"Authorization": "Bearer {{token}}"},
                },
            ]
        }
    )

    asyncio.run(api_executor.run_api_case(_FakeDB(), _run_stub(), case, {}))

    assert fake_http.requests[0]["url"].endswith("/users/u-2")
    assert fake_http.requests[1]["headers"]["Authorization"] == "Bearer tok-2"


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


def test_graphql_executor_oauth2_client_credentials_adds_authorization(fake_http, monkeypatch):
    _events_recorder(monkeypatch, graphql_executor)
    fake_http.script = [
        _FakeResponse(200, {"access_token": "gql-token"}),
        _FakeResponse(200, {"data": {"ping": True}}),
    ]
    case = _Obj(
        config={
            "steps": [
                {
                    "endpoint": "https://gql.example.com",
                    "query": "{ ping }",
                    "auth": {
                        "type": "oauth2_client_credentials",
                        "token_url": "https://issuer.example.com/oauth/token",
                        "client_id": "client-1",
                        "client_secret": "secret-1",
                    },
                }
            ]
        }
    )

    asyncio.run(graphql_executor.run_graphql_case(_FakeDB(), _run_stub(), case, {}))

    assert fake_http.requests[0]["url"] == "https://issuer.example.com/oauth/token"
    assert fake_http.requests[1]["headers"]["Authorization"] == "Bearer gql-token"


def test_graphql_executor_digest_auth_is_passed_to_httpx(fake_http, monkeypatch):
    _events_recorder(monkeypatch, graphql_executor)
    marker = object()
    monkeypatch.setattr(graphql_executor, "build_digest_auth", lambda *_args: marker)
    fake_http.script = [_FakeResponse(200, {"data": {"ping": True}})]
    case = _Obj(
        config={
            "steps": [
                {
                    "endpoint": "https://gql.example.com",
                    "query": "{ ping }",
                    "auth": {"type": "digest", "username": "u", "password": "p"},
                }
            ]
        }
    )

    asyncio.run(graphql_executor.run_graphql_case(_FakeDB(), _run_stub(), case, {}))

    assert fake_http.requests[0]["auth"] is marker


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

_STREAM_PROTO = """
syntax = "proto3";
package demo;
message EchoRequest { string text = 1; }
message EchoReply { string text = 1; }
service Echo {
  rpc List (EchoRequest) returns (stream EchoReply);
  rpc Collect (stream EchoRequest) returns (EchoReply);
  rpc Chat (stream EchoRequest) returns (stream EchoReply);
}
"""


def test_grpc_compile_proto_rejects_bad_syntax():
    with pytest.raises(RuntimeError, match="Proto 编译失败"):
        grpc_executor._compile_proto("syntax = broken")


def test_grpc_compile_proto_supports_imported_files():
    content = """
syntax = "proto3";
package demo;
import "common/types.proto";
message Request { common.Shared shared = 1; }
"""
    desc_set = grpc_executor._compile_proto(
        content,
        {"common/types.proto": 'syntax = "proto3"; package common; message Shared { string id = 1; }'},
    )

    assert {item.name for item in desc_set.file} == {"service.proto", "common/types.proto"}


@pytest.mark.parametrize(
    "filename", ["../escape.proto", "/tmp/escape.proto", "common/../escape.proto", "common\\..\\escape.proto"]
)
def test_grpc_compile_proto_rejects_unsafe_import_paths(filename):
    with pytest.raises(RuntimeError, match="Proto import 文件名不安全"):
        grpc_executor._compile_proto('syntax = "proto3";', {filename: 'syntax = "proto3";'})


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


class _FakeStreamingChannel:
    def __init__(self, response_factory):
        self.response_factory = response_factory
        self.closed = False
        self.calls = []

    def unary_stream(self, method_path, request_serializer=None, response_deserializer=None):
        def call(request_msg, timeout=None, metadata=None):
            self.calls.append(
                {"mode": "server_stream", "path": method_path, "request": request_msg, "metadata": metadata}
            )

            async def responses():
                for response in self.response_factory("server_stream", [request_msg]):
                    yield response

            return responses()

        return call

    def stream_unary(self, method_path, request_serializer=None, response_deserializer=None):
        async def call(request_iterator, timeout=None, metadata=None):
            requests = [request async for request in request_iterator]
            self.calls.append({"mode": "client_stream", "path": method_path, "request": requests, "metadata": metadata})
            return self.response_factory("client_stream", requests)[0]

        return call

    def stream_stream(self, method_path, request_serializer=None, response_deserializer=None):
        def call(request_iterator, timeout=None, metadata=None):
            async def responses():
                requests = [request async for request in request_iterator]
                self.calls.append(
                    {"mode": "bidi_stream", "path": method_path, "request": requests, "metadata": metadata}
                )
                for response in self.response_factory("bidi_stream", requests):
                    yield response

            return responses()

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


def test_grpc_executor_compiles_imported_proto_files(monkeypatch):
    _events_recorder(monkeypatch, grpc_executor)

    main_proto = """
syntax = "proto3";
package demo;
import "common/types.proto";
message EchoRequest { common.Shared shared = 1; }
message EchoReply { string text = 1; }
    service Echo { rpc Say (EchoRequest) returns (EchoReply); }
"""
    from google.protobuf import message_factory

    def responder(request_msg):
        assert request_msg.shared.id == "42"
        pool = request_msg.DESCRIPTOR.file.pool
        RespClass = message_factory.GetMessageClass(pool.FindMessageTypeByName("demo.EchoReply"))
        return RespClass(text="imported")

    channel = _install_grpc_channel(monkeypatch, responder)
    case = _Obj(
        config={
            "steps": [
                {
                    "target": "localhost:50051",
                    "proto_content": main_proto,
                    "proto_files": {
                        "common/types.proto": 'syntax = "proto3"; package common; message Shared { string id = 1; }'
                    },
                    "service": "demo.Echo",
                    "method": "Say",
                    "request_json": '{"shared":{"id":"42"}}',
                }
            ]
        }
    )
    run = _run_stub()
    asyncio.run(grpc_executor.run_grpc_case(_FakeDB(), run, case, {}))

    assert run.status is RunStatus.passed
    assert channel.calls[0]["path"] == "/demo.Echo/Say"


def _stream_case(method: str, request_json: str, assertions=None):
    return _Obj(
        config={
            "steps": [
                {
                    "target": "localhost:50051",
                    "proto_content": _STREAM_PROTO,
                    "service": "demo.Echo",
                    "method": method,
                    "request_json": request_json,
                    "assertions": assertions or [],
                }
            ]
        }
    )


def _stream_channel(monkeypatch, response_factory):
    channel = _FakeStreamingChannel(response_factory)
    monkeypatch.setattr(grpc_executor.grpc.aio, "insecure_channel", lambda target: channel)
    return channel


def test_grpc_executor_supports_server_streaming(monkeypatch):
    _events_recorder(monkeypatch, grpc_executor)

    def response_factory(_mode, requests):
        from google.protobuf import message_factory

        pool = requests[0].DESCRIPTOR.file.pool
        RespClass = message_factory.GetMessageClass(pool.FindMessageTypeByName("demo.EchoReply"))
        return [RespClass(text="first"), RespClass(text="second")]

    channel = _stream_channel(monkeypatch, response_factory)
    run = _run_stub()
    db = _FakeDB()
    case = _stream_case(
        "List",
        '{"text":"hello"}',
        [{"target": "body", "operator": "eq", "expected": "second", "expression": "$[1].text"}],
    )

    asyncio.run(grpc_executor.run_grpc_case(db, run, case, {}))

    assert run.status is RunStatus.passed
    assert channel.calls[0]["mode"] == "server_stream"
    assert db.added[0].response_data["grpc_mode"] == "server_stream"
    assert len(db.added[0].response_data["body"]) == 2


def test_grpc_executor_supports_client_streaming_with_json_array(monkeypatch):
    _events_recorder(monkeypatch, grpc_executor)

    def response_factory(_mode, requests):
        from google.protobuf import message_factory

        pool = requests[0].DESCRIPTOR.file.pool
        RespClass = message_factory.GetMessageClass(pool.FindMessageTypeByName("demo.EchoReply"))
        return [RespClass(text="|".join(request.text for request in requests))]

    channel = _stream_channel(monkeypatch, response_factory)
    run = _run_stub()
    db = _FakeDB()
    case = _stream_case(
        "Collect",
        '[{"text":"a"},{"text":"b"}]',
        [{"target": "body", "operator": "eq", "expected": "a|b", "expression": "$.text"}],
    )

    asyncio.run(grpc_executor.run_grpc_case(db, run, case, {}))

    assert run.status is RunStatus.passed
    assert channel.calls[0]["mode"] == "client_stream"
    assert [request.text for request in channel.calls[0]["request"]] == ["a", "b"]


def test_grpc_executor_supports_bidi_streaming(monkeypatch):
    _events_recorder(monkeypatch, grpc_executor)

    def response_factory(_mode, requests):
        from google.protobuf import message_factory

        pool = requests[0].DESCRIPTOR.file.pool
        RespClass = message_factory.GetMessageClass(pool.FindMessageTypeByName("demo.EchoReply"))
        return [RespClass(text=f"reply:{request.text}") for request in requests]

    channel = _stream_channel(monkeypatch, response_factory)
    run = _run_stub()
    db = _FakeDB()
    case = _stream_case(
        "Chat",
        '[{"text":"one"},{"text":"two"}]',
        [{"target": "body", "operator": "contains", "expected": "reply:two", "expression": "$[1].text"}],
    )

    asyncio.run(grpc_executor.run_grpc_case(db, run, case, {}))

    assert run.status is RunStatus.passed
    assert channel.calls[0]["mode"] == "bidi_stream"
    assert db.added[0].response_data["grpc_mode"] == "bidi_stream"


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

    def fake_secure_channel(target, creds, options=None):
        secure_calls.append({"target": target, "creds": creds, "options": options})
        return channel

    credential_calls = []

    def fake_ssl_channel_credentials(root_certificates=None):
        credential_calls.append(root_certificates)
        return "creds"

    monkeypatch.setattr(grpc_executor.grpc, "ssl_channel_credentials", fake_ssl_channel_credentials, raising=False)
    monkeypatch.setattr(grpc_executor.grpc.aio, "secure_channel", fake_secure_channel)
    case = _grpc_case()
    case.config["steps"][0]["use_tls"] = True
    case.config["steps"][0]["request_json"] = "{broken"  # 走到 channel 创建前的错误即可，不实际调用

    asyncio.run(grpc_executor.run_grpc_case(_FakeDB(), _run_stub(), case, {"word": "x"}))

    # request_json 在 channel 创建之前失败，TLS 分支不应被触达；改用合法 JSON 再驱动一次
    case2 = _grpc_case(assertions=[{"target": "grpc_status", "operator": "eq", "expected": "OK"}])
    case2.config["steps"][0]["use_tls"] = True
    case2.config["steps"][0]["tls_root_certificates"] = (
        "-----BEGIN CERTIFICATE-----\npublic-ca\n-----END CERTIFICATE-----"
    )
    case2.config["steps"][0]["tls_server_name"] = "grpc-target"

    def responder(request_msg):
        from google.protobuf import message_factory

        pool = request_msg.DESCRIPTOR.file.pool
        RespClass = message_factory.GetMessageClass(pool.FindMessageTypeByName("demo.EchoReply"))
        return RespClass(text="ok")

    channel.responder = responder
    run = _run_stub()
    db = _FakeDB()
    asyncio.run(grpc_executor.run_grpc_case(db, run, case2, {"word": "x"}))

    assert secure_calls[-1]["target"] == "localhost:50051"
    assert secure_calls[-1]["options"] == (("grpc.ssl_target_name_override", "grpc-target"),)
    assert credential_calls[-1] == b"-----BEGIN CERTIFICATE-----\npublic-ca\n-----END CERTIFICATE-----"
    assert db.added[0].request_data["tls_root_certificate_configured"] is True
    assert "tls_root_certificates" not in db.added[0].request_data
    assert run.status is RunStatus.passed


def test_grpc_executor_rejects_private_key_in_tls_root_certificates(monkeypatch):
    _events_recorder(monkeypatch, grpc_executor)
    case = _grpc_case()
    case.config["steps"][0]["use_tls"] = True
    case.config["steps"][0]["tls_root_certificates"] = (
        "-----BEGIN CERTIFICATE-----\npublic-ca\n-----END CERTIFICATE-----\n"
        "-----BEGIN PRIVATE KEY-----\nsecret\n-----END PRIVATE KEY-----"
    )
    db = _FakeDB()
    run = _run_stub()

    asyncio.run(grpc_executor.run_grpc_case(db, run, case, {"word": "x"}))

    assert db.added[0].status is RunStatus.error
    assert "不能包含私钥" in db.added[0].error_message


@pytest.mark.parametrize("module", [api_executor, graphql_executor, websocket_executor, grpc_executor])
def test_executor_safe_publish_swallows_redis_failures(monkeypatch, module):
    async def broken_publish(_run_id, _payload):
        raise RuntimeError("redis down")

    monkeypatch.setattr(module, "publish_run_event", broken_publish)
    asyncio.run(module._safe_publish_run_event(1, {"type": "step_result"}))
