import asyncio
import sys
import types
from pathlib import Path

import pytest
from fastapi import HTTPException
from pydantic import ValidationError

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))


def _fake_get_current_user():
    return None


def _fake_require_engineer():
    return None


sys.modules["app.core.database"] = types.SimpleNamespace(
    get_db=lambda: None,
    AsyncSessionLocal=lambda: None,
)


def _p3c_noop(*_a, **_kw):
    return None


async def _p3c_noop_async(*_a, **_kw):
    return None


sys.modules["app.api.deps"] = types.SimpleNamespace(
    get_current_user=_fake_get_current_user,
    require_engineer=_fake_require_engineer,
    require_admin=_p3c_noop,
    require_project_access=lambda *a, **kw: _p3c_noop,
    assert_project_access=_p3c_noop_async,
    ProjectRole=type("ProjectRole", (), {"owner": "owner", "editor": "editor", "viewer": "viewer"}),
)
sys.modules["app.core.redis_client"] = types.SimpleNamespace(
    get_json_cache=lambda *args, **kwargs: None,
    set_json_cache=lambda *args, **kwargs: None,
    delete_json_cache=lambda *args, **kwargs: None,
    delete_json_cache_pattern=lambda *args, **kwargs: None,
)

from app.api.v1 import mock_rules
from app.models.mock import MockMethod
from app.schemas.mock import MockAIGenerateIn, MockRuleCreate, MockRuleUpdate


class _FakeDB:
    def __init__(self, project=None):
        self._project = project
        self.added = []
        self.committed = False

    async def get(self, model, _pk):
        if getattr(model, "__name__", "") == "Project":
            return self._project
        return None

    def add(self, obj):
        self.added.append(obj)

    async def commit(self):
        self.committed = True

    async def refresh(self, obj):
        if getattr(obj, "id", None) is None:
            obj.id = 101


def test_mock_rule_create_normalizes_path():
    body = MockRuleCreate(
        name="rule",
        project_id=1,
        method=MockMethod.GET,
        path="api/pay",
    )

    assert body.path == "/api/pay"


def test_mock_rule_update_normalizes_path():
    body = MockRuleUpdate(path="health/check")

    assert body.path == "/health/check"


def test_mock_conditions_accept_supported_operators():
    body = MockRuleCreate(
        name="conditional",
        project_id=1,
        method=MockMethod.GET,
        path="/health",
        match_conditions={
            "query": {"scene": {"$in": ["success", "pending"]}},
            "headers": {"x-request-id": {"$contains": "test-"}},
            "body": {"token": {"$exists": True}},
        },
    )

    assert body.match_conditions.query["scene"] == {"$in": ["success", "pending"]}


@pytest.mark.parametrize(
    "match_conditions",
    [
        {"query": {"scene": {"$unknown": "success"}}},
        {"query": {"scene": {"$exists": "yes"}}},
        {"query": {"scene": {"$contains": ["success"]}}},
        {"query": {"scene": {"$in": [{"nested": True}]}}},
    ],
)
def test_mock_conditions_reject_unsupported_operator_shapes(match_conditions):
    with pytest.raises(ValidationError):
        MockRuleCreate(
            name="invalid-conditional",
            project_id=1,
            method=MockMethod.GET,
            path="/health",
            match_conditions=match_conditions,
        )


def test_create_mock_rule_returns_404_for_missing_project():
    body = MockRuleCreate(
        name="rule",
        project_id=999,
        method=MockMethod.GET,
        path="/api/pay",
    )
    db = _FakeDB(project=None)
    current_user = types.SimpleNamespace(id=7)

    with pytest.raises(HTTPException) as exc:
        asyncio.run(mock_rules.create_mock_rule(body=body, db=db, current_user=current_user))

    assert exc.value.status_code == 404
    assert not db.added
    assert db.committed is False


def test_mock_ai_generate_request_limits_rule_ids_and_count():
    body = MockAIGenerateIn(project_id=1, rule_ids=list(range(20)), rule_count=20)

    assert len(body.rule_ids) == 20
    assert body.rule_count == 20
