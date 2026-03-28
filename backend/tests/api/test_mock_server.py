import asyncio
import json
import sys
import types
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

sys.modules["app.core.database"] = types.SimpleNamespace(AsyncSessionLocal=lambda: None)
sys.modules["app.core.redis_client"] = types.SimpleNamespace(
    get_json_cache=lambda *args, **kwargs: None,
    set_json_cache=lambda *args, **kwargs: None,
    delete_json_cache=lambda *args, **kwargs: None,
    delete_json_cache_pattern=lambda *args, **kwargs: None,
)

from app.api.v1 import mock_server
from app.models.mock import MockMethod


class _FakeExecuteResult:
    def __init__(self, rules=None):
        self._rules = rules or []

    def scalar_one_or_none(self):
        return self._rules[0] if self._rules else None

    def scalars(self):
        return types.SimpleNamespace(all=lambda: self._rules)


class _FakeSession:
    def __init__(self, rules=None, rule_by_id=None):
        self._rules = rules or []
        self._rule_by_id = rule_by_id or {}
        self.committed = False

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        return False

    async def execute(self, stmt):
        return _FakeExecuteResult(self._rules)

    async def get(self, _model, rule_id):
        return self._rule_by_id.get(rule_id)

    async def commit(self):
        self.committed = True


class _FakeRequest:
    def __init__(self, method="GET", query=None, headers=None, body=None):
        self.method = method
        self.query_params = query or {}
        self.headers = headers or {}
        self._body = body or b""

    async def body(self):
        return self._body


@pytest.mark.parametrize(
    ("conditions", "request_data", "expected"),
    [
        ({"query": {"scene": "success"}}, {"query": {"scene": "success"}, "headers": {}, "body": {}}, True),
        ({"headers": {"x-env": "test"}}, {"query": {}, "headers": {"x-env": "test"}, "body": {}}, True),
        ({"body": {"status": "paid"}}, {"query": {}, "headers": {}, "body": {"status": "paid"}}, True),
        ({"query": {"scene": "fail"}}, {"query": {"scene": "success"}, "headers": {}, "body": {}}, False),
    ],
)
def test_match_conditions(conditions, request_data, expected):
    rule = types.SimpleNamespace(match_conditions=conditions)
    assert mock_server._match_conditions(rule, request_data) is expected


def test_build_rule_stmt_prefers_exact_method_over_any():
    stmt = mock_server._build_rule_stmt(
        project_id=9,
        candidate_methods=[MockMethod.GET, MockMethod.ANY],
    )
    assert stmt is not None


def test_mock_endpoint_handles_head_and_options_without_crashing(monkeypatch):
    responses = []

    def fake_session_factory():
        return _FakeSession(rules=[])

    async def fake_get_json_cache(*_args, **_kwargs):
        return None

    async def fake_set_json_cache(*_args, **_kwargs):
        return None

    monkeypatch.setattr(mock_server, "AsyncSessionLocal", fake_session_factory)
    monkeypatch.setattr(mock_server, "get_json_cache", fake_get_json_cache)
    monkeypatch.setattr(mock_server, "set_json_cache", fake_set_json_cache)

    for method in ["HEAD", "OPTIONS"]:
        response = asyncio.run(
            mock_server.mock_endpoint(
                project_id=7,
                path="health",
                request=_FakeRequest(method=method),
            )
        )
        responses.append((method, response))

    for method, response in responses:
        assert response.status_code == 404
        payload = json.loads(response.body.decode("utf-8"))
        assert payload["detail"] == f"No mock rule matched: {method} /health"


def test_path_matches_template_supports_placeholder_segments():
    assert mock_server._path_matches_template("/api/users/{id}", "/api/users/42") is True
    assert mock_server._path_matches_template("/api/users/{id}", "/api/orders/42") is False


def test_find_matching_rule_checks_conditions(monkeypatch):
    matching_rule = types.SimpleNamespace(
        id=2,
        path="/api/pay",
        method=MockMethod.GET,
        is_enabled=True,
        match_conditions={"query": {"scene": "success"}},
    )

    def fake_session_factory():
        return _FakeSession(rules=[matching_rule])

    async def fake_get_json_cache(*_args, **_kwargs):
        return None

    async def fake_set_json_cache(*_args, **_kwargs):
        return None

    monkeypatch.setattr(mock_server, "AsyncSessionLocal", fake_session_factory)
    monkeypatch.setattr(mock_server, "get_json_cache", fake_get_json_cache)
    monkeypatch.setattr(mock_server, "set_json_cache", fake_set_json_cache)

    result = asyncio.run(
        mock_server._find_matching_rule(
            project_id=1,
            normalized="/api/pay",
            candidate_methods=[MockMethod.GET, MockMethod.ANY],
            request_data={"query": {"scene": "success"}, "headers": {}, "body": {}},
        )
    )

    assert result is matching_rule


def test_find_matching_rule_revalidates_cached_rule_before_reuse(monkeypatch):
    cached_rule = types.SimpleNamespace(
        id=7,
        path="/api/pay",
        method=MockMethod.GET,
        is_enabled=False,
        match_conditions={"query": {"scene": "success"}},
    )
    deleted_keys = []

    def fake_session_factory():
        return _FakeSession(rules=[], rule_by_id={7: cached_rule})

    async def fake_get_json_cache(*_args, **_kwargs):
        return {"rule_id": 7}

    async def fake_set_json_cache(*_args, **_kwargs):
        return None

    async def fake_delete_json_cache(key, *_args, **_kwargs):
        deleted_keys.append(key)

    monkeypatch.setattr(mock_server, "AsyncSessionLocal", fake_session_factory)
    monkeypatch.setattr(mock_server, "get_json_cache", fake_get_json_cache)
    monkeypatch.setattr(mock_server, "set_json_cache", fake_set_json_cache)
    monkeypatch.setattr(mock_server, "delete_json_cache", fake_delete_json_cache)

    result = asyncio.run(
        mock_server._find_matching_rule(
            project_id=1,
            normalized="/api/pay",
            candidate_methods=[MockMethod.GET, MockMethod.ANY],
            request_data={"query": {"scene": "success"}, "headers": {}, "body": {}},
        )
    )

    assert result is None
    assert deleted_keys


def test_render_template_text_supports_request_placeholders():
    rendered = mock_server._render_template_text(
        '{"user": "{{query.user}}", "env": "{{headers.x-env}}", "status": "{{body.status}}"}',
        {
            "query": {"user": "alice"},
            "headers": {"x-env": "test"},
            "body": {"status": "paid"},
        },
    )
    assert "alice" in rendered
    assert "test" in rendered
    assert "paid" in rendered


def test_record_sample_appends_latest_request(monkeypatch):
    rule = types.SimpleNamespace(id=5, record_requests=True, recorded_samples=[])
    session = _FakeSession(rule_by_id={5: rule})

    def fake_session_factory():
        return session

    monkeypatch.setattr(mock_server, "AsyncSessionLocal", fake_session_factory)

    asyncio.run(
        mock_server._record_sample(
            5,
            {"query": {"scene": "success"}, "headers": {}, "body": {}},
            {"status_code": 200, "headers": {}, "body": '{"ok": true}'},
        )
    )

    assert len(rule.recorded_samples) == 1
    assert rule.recorded_samples[0]["request"]["query"]["scene"] == "success"
    assert session.committed is True


def test_mock_endpoint_renders_template_response(monkeypatch):
    rule = types.SimpleNamespace(
        id=3,
        name="模板规则",
        status_code=200,
        response_headers={"Content-Type": "application/json"},
        response_body='{"user": "{{query.user}}"}',
        render_template=True,
        record_requests=False,
        delay_ms=0,
    )

    async def fake_find_matching_rule(*_args, **_kwargs):
        return rule

    monkeypatch.setattr(mock_server, "_find_matching_rule", fake_find_matching_rule)

    response = asyncio.run(
        mock_server.mock_endpoint(
            project_id=1,
            path="users",
            request=_FakeRequest(method="GET", query={"user": "bob"}),
        )
    )

    assert response.status_code == 200
    assert b"bob" in response.body
