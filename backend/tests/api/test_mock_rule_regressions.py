import asyncio
import sys
import types
from pathlib import Path

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
from app.schemas.mock import MockAIGenerateIn, MockRuleCreate, MockRulesImportRequest


class _FakeMockRule:
    def __init__(self, **kwargs):
        for key, value in kwargs.items():
            setattr(self, key, value)
        self.id = None


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


def test_import_mock_rules_overrides_embedded_project_id(monkeypatch):
    invalidations = []

    async def fake_invalidate(project_id):
        invalidations.append(project_id)

    monkeypatch.setattr(mock_rules, "MockRule", _FakeMockRule)
    monkeypatch.setattr(mock_rules, "invalidate_mock_cache", fake_invalidate)

    db = _FakeDB(project=types.SimpleNamespace(id=5))
    current_user = types.SimpleNamespace(id=7)
    body = MockRulesImportRequest(
        project_id=5,
        rules=[
            MockRuleCreate(
                name="rule",
                project_id=1,
                method=MockMethod.GET,
                path="/api/pay",
            )
        ],
    )

    rules = asyncio.run(mock_rules.import_mock_rules(body=body, db=db, current_user=current_user))

    assert db.committed is True
    assert len(rules) == 1
    assert db.added[0].project_id == 5
    assert invalidations == [5]


def test_mock_ai_generate_returns_drafts_without_persisting(monkeypatch):
    class _AIFakeDB:
        committed = False

        async def get(self, model, pk):
            model_name = getattr(model, "__name__", "")
            if model_name == "Project":
                return types.SimpleNamespace(id=5, ai_llm_config_id=11)
            if model_name == "AILLMConfig":
                return types.SimpleNamespace(id=11, enabled=True)
            if model_name == "MockRule":
                return types.SimpleNamespace(
                    id=8,
                    project_id=5,
                    name="Users",
                    method=MockMethod.GET,
                    path="/api/users",
                    status_code=200,
                    response_headers={},
                    response_body='{"ok":true}',
                    match_conditions={"query": {}, "headers": {}, "body": {}},
                    delay_ms=0,
                    recorded_samples=[],
                )
            return None

    async def fake_generate(**_kwargs):
        return (
            [
                {
                    "name": "Generated users",
                    "method": "GET",
                    "path": "/api/users/generated",
                    "status_code": 200,
                    "response_headers": {"Content-Type": "application/json"},
                    "response_body": '{"ok":true}',
                    "match_conditions": {"query": {}, "headers": {}, "body": {}},
                    "delay_ms": 0,
                    "is_enabled": True,
                    "render_template": False,
                    "record_requests": False,
                }
            ],
            [],
        )

    monkeypatch.setattr(mock_rules, "generate_mock_rule_drafts", fake_generate)
    result = asyncio.run(
        mock_rules.generate_mock_rules_with_ai(
            body=MockAIGenerateIn(project_id=5, rule_ids=[8], requirement="success", rule_count=1),
            db=_AIFakeDB(),
            current_user=types.SimpleNamespace(id=7),
        )
    )

    assert result.project_id == 5
    assert result.rules[0].path == "/api/users/generated"
