import asyncio
import json
import sys
import types
from pathlib import Path

from sqlalchemy.sql import operators


sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

sys.modules["app.core.database"] = types.SimpleNamespace(AsyncSessionLocal=lambda: None)

from app.api.v1 import mock_server
from app.models.mock import MockMethod


class _FakeExecuteResult:
    def __init__(self, rule=None):
        self._rule = rule

    def scalar_one_or_none(self):
        return self._rule

    def scalars(self):
        return types.SimpleNamespace(all=lambda: [] if self._rule is None else [self._rule])


class _FakeSession:
    def __init__(self, rule=None):
        self._rule = rule
        self.statements = []

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        return False

    async def execute(self, stmt):
        self.statements.append(stmt)
        return _FakeExecuteResult(self._rule)


def test_build_rule_stmt_prefers_exact_method_over_any():
    stmt = mock_server._build_rule_stmt(
        project_id=9,
        normalized="/api/ping",
        candidate_methods=[MockMethod.GET, MockMethod.ANY],
    )

    order_clause = list(stmt._order_by_clauses)[0]

    assert order_clause.operator is operators.eq
    assert order_clause.right.value == MockMethod.ANY


def test_mock_endpoint_handles_head_and_options_without_crashing(monkeypatch):
    responses = []

    def fake_session_factory():
        return _FakeSession(rule=None)

    monkeypatch.setattr(mock_server, "AsyncSessionLocal", fake_session_factory)

    for method in ["HEAD", "OPTIONS"]:
        response = asyncio.run(
            mock_server.mock_endpoint(
                project_id=7,
                path="health",
                request=types.SimpleNamespace(method=method),
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
