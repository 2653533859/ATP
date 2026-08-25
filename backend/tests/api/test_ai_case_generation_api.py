"""Tests for app.api.v1.ai_case_generation."""

import asyncio
import inspect
import json
import sys
import types
from datetime import datetime, timezone
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from tests.api.conftest import fake_require_admin as _fake_require_admin
from tests.api.conftest import fake_require_engineer as _fake_require_engineer

sys.modules["app.core.database"] = types.SimpleNamespace(get_db=lambda: None)


def _p3c_noop(*_a, **_kw):
    return None


async def _p3c_noop_async(*_a, **_kw):
    return None


sys.modules["app.api.deps"] = types.SimpleNamespace(
    require_admin=_fake_require_admin,
    require_engineer=_fake_require_engineer,
    get_current_user=lambda: None,
    require_project_access=lambda *a, **kw: _p3c_noop,
    assert_project_access=_p3c_noop_async,
    ProjectRole=type("ProjectRole", (), {"owner": "owner", "editor": "editor", "viewer": "viewer"}),
)

from app.models.bootstrap import load_all_models

load_all_models()

from app.api.v1 import ai_case_generation
from app.schemas.ai_case import AICaseGenerateIn, AIParseSchemaIn
from app.services.ai_case.generator import GenerationResult


def test_endpoints_require_engineer():
    for fn in (
        ai_case_generation.parse_schema_endpoint,
        ai_case_generation.generate_cases_endpoint,
    ):
        dep = inspect.signature(fn).parameters["user"].default.dependency
        assert dep is _fake_require_engineer


def test_parse_schema_endpoint_openapi_success():
    doc = {
        "openapi": "3.0.0",
        "paths": {
            "/health": {"get": {"summary": "Health"}},
        },
    }
    body = AIParseSchemaIn(source_type="openapi", content=json.dumps(doc))
    result = asyncio.run(ai_case_generation.parse_schema_endpoint(body=body, user=None))
    assert len(result.endpoints) == 1
    assert result.endpoints[0].method == "GET"
    assert result.endpoints[0].path == "/health"


def test_parse_schema_endpoint_invalid_returns_400():
    body = AIParseSchemaIn(source_type="curl", content="totally not curl")
    try:
        asyncio.run(ai_case_generation.parse_schema_endpoint(body=body, user=None))
    except Exception as exc:
        assert getattr(exc, "status_code", None) == 400
    else:
        raise AssertionError("应抛 400")


class _ScalarResult:
    def __init__(self, rows):
        self._rows = rows

    def all(self):
        return self._rows


class _ExecuteResult:
    def __init__(self, rows):
        self._rows = rows

    def scalars(self):
        return _ScalarResult(self._rows)


class _FunnelDB:
    async def execute(self, _stmt):
        return _ExecuteResult(
            [
                types.SimpleNamespace(
                    action="ai_case_generate",
                    detail='{"draft_count": 3, "warning_count": 1}',
                    created_at=datetime(2026, 5, 29, tzinfo=timezone.utc),
                ),
                types.SimpleNamespace(
                    action="ai_case_draft_saved",
                    detail='{"saved_count": 2}',
                    created_at=datetime(2026, 5, 29, 1, tzinfo=timezone.utc),
                ),
            ]
        )


def test_funnel_stats_endpoint_returns_aggregate():
    result = asyncio.run(ai_case_generation.get_ai_case_funnel_stats(days=30, db=_FunnelDB(), _=None))
    assert result.generated_sessions == 1
    assert result.generated_drafts == 3
    assert result.saved_drafts == 2
    assert result.warning_count == 1
    assert result.save_rate == 66.67


class _AsyncDB:
    def __init__(self, get_value_map):
        self._map = get_value_map
        self.added = []
        self.commits = 0

    async def get(self, model, pk):
        return self._map.get(model.__name__, {}).get(pk)

    def add(self, obj):
        self.added.append(obj)

    async def flush(self):
        return None

    async def commit(self):
        self.commits += 1


class _VersionAsyncDB(_AsyncDB):
    def __init__(self, get_value_map, version):
        super().__init__(get_value_map)
        self.version = version

    async def execute(self, _statement):
        return types.SimpleNamespace(scalar_one_or_none=lambda: self.version)


def _fake_project(project_id=1, ai_llm_config_id: int | None = 1):
    return types.SimpleNamespace(id=project_id, ai_llm_config_id=ai_llm_config_id)


def _fake_config(config_id=1, enabled=True):
    return types.SimpleNamespace(
        id=config_id,
        name="dp",
        provider="deepseek",
        api_key_encrypted="enc",
        endpoint=None,
        model_name="deepseek-chat",
        default_params={},
        enabled=enabled,
        description=None,
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )


def _fake_module(module_id=1, project_id=1):
    return types.SimpleNamespace(id=module_id, project_id=project_id)


def test_generate_404_when_project_missing():
    db = _AsyncDB({"Project": {}, "AILLMConfig": {1: _fake_config()}})
    body = AICaseGenerateIn(project_id=999, module_id=1)
    try:
        asyncio.run(ai_case_generation.generate_cases_endpoint(body=body, db=db, user=None))
    except Exception as exc:
        assert getattr(exc, "status_code", None) == 404
    else:
        raise AssertionError("应 404")


def test_generate_400_when_project_has_no_ai_config():
    db = _AsyncDB(
        {
            "Project": {1: _fake_project(ai_llm_config_id=None)},
            "Module": {1: _fake_module()},
        }
    )
    body = AICaseGenerateIn(project_id=1, module_id=1)
    try:
        asyncio.run(ai_case_generation.generate_cases_endpoint(body=body, db=db, user=None))
    except Exception as exc:
        assert getattr(exc, "status_code", None) == 400
        assert "未配置" in exc.detail  # type: ignore[attr-defined]
    else:
        raise AssertionError("应 400")


def test_generate_404_when_module_missing():
    db = _AsyncDB({"Project": {1: _fake_project()}, "Module": {}})
    body = AICaseGenerateIn(project_id=1, module_id=999)
    try:
        asyncio.run(ai_case_generation.generate_cases_endpoint(body=body, db=db, user=None))
    except Exception as exc:
        assert getattr(exc, "status_code", None) == 404
        assert "模块" in exc.detail  # type: ignore[attr-defined]
    else:
        raise AssertionError("应 404")


def test_generate_400_when_module_belongs_to_other_project():
    db = _AsyncDB(
        {
            "Project": {1: _fake_project()},
            "Module": {2: _fake_module(module_id=2, project_id=99)},
        }
    )
    body = AICaseGenerateIn(project_id=1, module_id=2)
    try:
        asyncio.run(ai_case_generation.generate_cases_endpoint(body=body, db=db, user=None))
    except Exception as exc:
        assert getattr(exc, "status_code", None) == 400
        assert "不属于当前项目" in exc.detail  # type: ignore[attr-defined]
    else:
        raise AssertionError("应 400")


def test_generate_400_when_config_disabled():
    db = _AsyncDB(
        {
            "Project": {1: _fake_project()},
            "Module": {1: _fake_module()},
            "AILLMConfig": {1: _fake_config(enabled=False)},
        }
    )
    body = AICaseGenerateIn(project_id=1, module_id=1)
    try:
        asyncio.run(ai_case_generation.generate_cases_endpoint(body=body, db=db, user=None))
    except Exception as exc:
        assert getattr(exc, "status_code", None) == 400
        assert "禁用" in exc.detail  # type: ignore[attr-defined]
    else:
        raise AssertionError("应 400")


def test_generate_success_invokes_generator(monkeypatch):
    db = _AsyncDB(
        {
            "Project": {1: _fake_project()},
            "Module": {2: _fake_module(module_id=2, project_id=1)},
            "AILLMConfig": {1: _fake_config()},
        }
    )

    called_with: dict = {}

    async def fake_generate(**kwargs):
        called_with.update(kwargs)
        return GenerationResult(
            drafts=[
                {
                    "name": "draft 1",
                    "summary": "s",
                    "description": None,
                    "case_type": "api",
                    "priority": "P2",
                    "case_level": "regression",
                    "tags": [],
                    "preconditions": [],
                    "postconditions": [],
                    "steps": [
                        {
                            "action": "GET /health",
                            "test_data": None,
                            "expected_result": "200",
                            "is_key_step": True,
                            "remarks": None,
                        }
                    ],
                    "config": {},
                }
            ],
            raw_text='[{"name":"draft 1"}]',
            warnings=[],
        )

    monkeypatch.setattr(ai_case_generation, "generate_case_drafts", fake_generate)

    body = AICaseGenerateIn(
        project_id=1,
        module_id=2,
        user_requirement="登录",
        max_cases=3,
    )
    result = asyncio.run(ai_case_generation.generate_cases_endpoint(body=body, db=db, user=None))

    assert result.project_id == 1
    assert result.module_id == 2
    assert len(result.drafts) == 1
    assert result.drafts[0].name == "draft 1"
    assert called_with["max_cases"] == 3
    assert called_with["user_requirement"] == "登录"
    assert db.added[-1].action == "ai_case_generate"
    assert db.added[-1].project_id == 1
    assert '"draft_count": 1' in db.added[-1].detail


def test_generate_passes_selected_dataset_and_mock_context(monkeypatch):
    dataset = types.SimpleNamespace(
        id=10,
        project_id=1,
        name="accounts",
        description="demo",
        format="json",
        validation_policy="hard",
        schema_fields=[{"name": "username", "type": "string", "required": True}],
        rows=[{"username": "alice_demo"}],
    )
    mock_rule = types.SimpleNamespace(
        id=20,
        project_id=1,
        name="login mock",
        method="POST",
        path="/login",
        status_code=200,
        response_headers={},
        response_body='{"ok":true}',
        match_conditions={},
        delay_ms=0,
        recorded_samples=[],
    )
    db = _AsyncDB(
        {
            "Project": {1: _fake_project()},
            "Module": {1: _fake_module()},
            "AILLMConfig": {1: _fake_config()},
            "TestDataset": {10: dataset},
            "MockRule": {20: mock_rule},
        }
    )
    called_with: dict = {}

    async def fake_generate(**kwargs):
        called_with.update(kwargs)
        return GenerationResult(drafts=[], raw_text="[]", warnings=[])

    monkeypatch.setattr(ai_case_generation, "generate_case_drafts", fake_generate)
    body = AICaseGenerateIn(project_id=1, module_id=1, dataset_id=10, mock_rule_ids=[20])

    asyncio.run(ai_case_generation.generate_cases_endpoint(body=body, db=db, user=None))

    assert called_with["dataset_id"] == 10
    assert called_with["dataset_context"]["name"] == "accounts"
    assert called_with["dataset_context"]["sample_rows"][0]["username"] == "alice_demo"
    assert called_with["mock_context"][0]["path"] == "/login"


def test_generate_uses_selected_immutable_dataset_version(monkeypatch):
    dataset = types.SimpleNamespace(
        id=10,
        project_id=1,
        name="accounts",
        description="current",
        format="json",
        validation_policy="soft",
        schema_fields=[{"name": "username", "type": "string", "required": True}],
        rows=[{"username": "current-user"}],
    )
    snapshot = types.SimpleNamespace(
        id=101,
        dataset_id=10,
        version=3,
        format="json",
        validation_policy="hard",
        schema_fields=[{"name": "username", "type": "string", "required": True}],
        rows=[{"username": "pinned-user"}],
    )
    mock_rule = types.SimpleNamespace(
        id=20,
        project_id=1,
        name="login mock",
        method="POST",
        path="/login",
        status_code=200,
        response_headers={},
        response_body='{"ok":true}',
        match_conditions={},
        delay_ms=0,
        recorded_samples=[],
    )
    db = _VersionAsyncDB(
        {
            "Project": {1: _fake_project()},
            "Module": {1: _fake_module()},
            "AILLMConfig": {1: _fake_config()},
            "TestDataset": {10: dataset},
            "MockRule": {20: mock_rule},
        },
        snapshot,
    )
    called_with: dict = {}

    async def fake_generate(**kwargs):
        called_with.update(kwargs)
        return GenerationResult(drafts=[], raw_text="[]", warnings=[])

    monkeypatch.setattr(ai_case_generation, "generate_case_drafts", fake_generate)
    body = AICaseGenerateIn(project_id=1, module_id=1, dataset_id=10, dataset_version=3, mock_rule_ids=[20, 20])

    asyncio.run(ai_case_generation.generate_cases_endpoint(body=body, db=db, user=None))

    assert called_with["dataset_version"] == 3
    assert called_with["dataset_context"]["version"] == 3
    assert called_with["dataset_context"]["sample_rows"][0]["username"] == "pinned-user"
    assert '"dataset_version": 3' in db.added[-1].detail
    assert '"mock_rule_ids": [20]' in db.added[-1].detail


def test_generate_rejects_context_from_another_project():
    dataset = types.SimpleNamespace(id=10, project_id=99)
    db = _AsyncDB(
        {
            "Project": {1: _fake_project()},
            "Module": {1: _fake_module()},
            "AILLMConfig": {1: _fake_config()},
            "TestDataset": {10: dataset},
        }
    )
    body = AICaseGenerateIn(project_id=1, module_id=1, dataset_id=10)

    with pytest.raises(Exception) as exc_info:
        asyncio.run(ai_case_generation.generate_cases_endpoint(body=body, db=db, user=None))

    assert getattr(exc_info.value, "status_code", None) == 400
    assert "不属于当前项目" in exc_info.value.detail  # type: ignore[attr-defined]


def test_generate_failure_writes_funnel_audit_event(monkeypatch):
    db = _AsyncDB(
        {
            "Project": {1: _fake_project()},
            "Module": {1: _fake_module()},
            "AILLMConfig": {1: _fake_config()},
        }
    )

    async def fake_generate(**kwargs):
        raise ai_case_generation.httpx.RequestError(
            "network down",
            request=ai_case_generation.httpx.Request("POST", "https://provider.test/v1/chat/completions"),
        )

    monkeypatch.setattr(ai_case_generation, "generate_case_drafts", fake_generate)

    body = AICaseGenerateIn(project_id=1, module_id=1)
    try:
        asyncio.run(ai_case_generation.generate_cases_endpoint(body=body, db=db, user=None))
    except Exception:
        pass

    assert db.added[-1].action == "ai_case_generate_failed"
    assert '"error_type": "network"' in db.added[-1].detail


def test_generate_502_on_llm_network_error(monkeypatch):
    db = _AsyncDB(
        {
            "Project": {1: _fake_project()},
            "Module": {1: _fake_module()},
            "AILLMConfig": {1: _fake_config()},
        }
    )

    async def fake_generate(**kwargs):
        raise ai_case_generation.httpx.RequestError(
            "network down",
            request=ai_case_generation.httpx.Request("POST", "https://provider.test/v1/chat/completions"),
        )

    monkeypatch.setattr(ai_case_generation, "generate_case_drafts", fake_generate)

    body = AICaseGenerateIn(project_id=1, module_id=1)
    try:
        asyncio.run(ai_case_generation.generate_cases_endpoint(body=body, db=db, user=None))
    except Exception as exc:
        assert getattr(exc, "status_code", None) == 502
        assert "网络请求失败" in exc.detail  # type: ignore[attr-defined]
    else:
        raise AssertionError("应 502")


def test_generate_400_on_value_error(monkeypatch):
    db = _AsyncDB(
        {
            "Project": {1: _fake_project()},
            "Module": {1: _fake_module()},
            "AILLMConfig": {1: _fake_config()},
        }
    )

    async def fake_generate(**kwargs):
        raise ValueError("API Key 解密失败")

    monkeypatch.setattr(ai_case_generation, "generate_case_drafts", fake_generate)

    body = AICaseGenerateIn(project_id=1, module_id=1)
    try:
        asyncio.run(ai_case_generation.generate_cases_endpoint(body=body, db=db, user=None))
    except Exception as exc:
        assert getattr(exc, "status_code", None) == 400
    else:
        raise AssertionError("应 400")


def test_generate_http_failure_does_not_expose_provider_body(monkeypatch):
    db = _AsyncDB(
        {
            "Project": {1: _fake_project()},
            "Module": {1: _fake_module()},
            "AILLMConfig": {1: _fake_config()},
        }
    )
    request = ai_case_generation.httpx.Request("POST", "https://provider.test/v1/chat/completions")
    response = ai_case_generation.httpx.Response(
        401,
        request=request,
        text='{"error":{"message":"invalid api_key=provider-secret"}}',
    )

    async def fake_generate(**kwargs):
        raise ai_case_generation.httpx.HTTPStatusError("provider rejected request", request=request, response=response)

    monkeypatch.setattr(ai_case_generation, "generate_case_drafts", fake_generate)

    with pytest.raises(Exception) as exc_info:
        asyncio.run(
            ai_case_generation.generate_cases_endpoint(
                body=AICaseGenerateIn(project_id=1, module_id=1), db=db, user=None
            )
        )

    detail = str(exc_info.value.detail)  # type: ignore[attr-defined]
    assert getattr(exc_info.value, "status_code", None) == 502
    assert "HTTP 401" in detail
    assert "provider-secret" not in detail
    assert "invalid api_key" not in detail


def test_generate_raw_response_is_bounded_and_redacted(monkeypatch):
    db = _AsyncDB(
        {
            "Project": {1: _fake_project()},
            "Module": {1: _fake_module()},
            "AILLMConfig": {1: _fake_config()},
        }
    )

    async def fake_generate(**kwargs):
        return GenerationResult(
            drafts=[],
            raw_text='{"password":"provider-secret","notes":"token=raw-secret"}',
            warnings=["LLM 未生成有效用例"],
        )

    monkeypatch.setattr(ai_case_generation, "generate_case_drafts", fake_generate)
    result = asyncio.run(
        ai_case_generation.generate_cases_endpoint(body=AICaseGenerateIn(project_id=1, module_id=1), db=db, user=None)
    )

    assert result.raw_response is not None
    assert "provider-secret" not in result.raw_response
    assert "raw-secret" not in result.raw_response
    assert "[已脱敏]" in result.raw_response
