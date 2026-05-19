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
sys.modules["app.api.deps"] = types.SimpleNamespace(
    require_admin=_fake_require_admin,
    require_engineer=_fake_require_engineer,
    get_current_user=lambda: None,
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
        dep = inspect.signature(fn).parameters["_"].default.dependency
        assert dep is _fake_require_engineer


def test_parse_schema_endpoint_openapi_success():
    doc = {
        "openapi": "3.0.0",
        "paths": {
            "/health": {"get": {"summary": "Health"}},
        },
    }
    body = AIParseSchemaIn(source_type="openapi", content=json.dumps(doc))
    result = asyncio.run(ai_case_generation.parse_schema_endpoint(body=body, _=None))
    assert len(result.endpoints) == 1
    assert result.endpoints[0].method == "GET"
    assert result.endpoints[0].path == "/health"


def test_parse_schema_endpoint_invalid_returns_400():
    body = AIParseSchemaIn(source_type="curl", content="totally not curl")
    try:
        asyncio.run(ai_case_generation.parse_schema_endpoint(body=body, _=None))
    except Exception as exc:
        assert getattr(exc, "status_code", None) == 400
    else:
        raise AssertionError("应抛 400")


class _AsyncDB:
    def __init__(self, get_value_map):
        self._map = get_value_map

    async def get(self, model, pk):
        return self._map.get(model.__name__, {}).get(pk)


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


def test_generate_404_when_project_missing():
    db = _AsyncDB({"Project": {}, "AILLMConfig": {1: _fake_config()}})
    body = AICaseGenerateIn(project_id=999, module_id=1)
    try:
        asyncio.run(ai_case_generation.generate_cases_endpoint(body=body, db=db, _=None))
    except Exception as exc:
        assert getattr(exc, "status_code", None) == 404
    else:
        raise AssertionError("应 404")


def test_generate_400_when_project_has_no_ai_config():
    db = _AsyncDB({"Project": {1: _fake_project(ai_llm_config_id=None)}})
    body = AICaseGenerateIn(project_id=1, module_id=1)
    try:
        asyncio.run(ai_case_generation.generate_cases_endpoint(body=body, db=db, _=None))
    except Exception as exc:
        assert getattr(exc, "status_code", None) == 400
        assert "未配置" in exc.detail  # type: ignore[attr-defined]
    else:
        raise AssertionError("应 400")


def test_generate_400_when_config_disabled():
    db = _AsyncDB(
        {
            "Project": {1: _fake_project()},
            "AILLMConfig": {1: _fake_config(enabled=False)},
        }
    )
    body = AICaseGenerateIn(project_id=1, module_id=1)
    try:
        asyncio.run(ai_case_generation.generate_cases_endpoint(body=body, db=db, _=None))
    except Exception as exc:
        assert getattr(exc, "status_code", None) == 400
        assert "禁用" in exc.detail  # type: ignore[attr-defined]
    else:
        raise AssertionError("应 400")


def test_generate_success_invokes_generator(monkeypatch):
    db = _AsyncDB(
        {
            "Project": {1: _fake_project()},
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
    result = asyncio.run(ai_case_generation.generate_cases_endpoint(body=body, db=db, _=None))

    assert result.project_id == 1
    assert result.module_id == 2
    assert len(result.drafts) == 1
    assert result.drafts[0].name == "draft 1"
    assert called_with["max_cases"] == 3
    assert called_with["user_requirement"] == "登录"


def test_generate_502_on_llm_network_error(monkeypatch):
    db = _AsyncDB(
        {
            "Project": {1: _fake_project()},
            "AILLMConfig": {1: _fake_config()},
        }
    )

    async def fake_generate(**kwargs):
        raise ai_case_generation.httpx.HTTPError("network down")

    monkeypatch.setattr(ai_case_generation, "generate_case_drafts", fake_generate)

    body = AICaseGenerateIn(project_id=1, module_id=1)
    try:
        asyncio.run(ai_case_generation.generate_cases_endpoint(body=body, db=db, _=None))
    except Exception as exc:
        assert getattr(exc, "status_code", None) == 502
        assert "网络错误" in exc.detail  # type: ignore[attr-defined]
    else:
        raise AssertionError("应 502")


def test_generate_400_on_value_error(monkeypatch):
    db = _AsyncDB(
        {
            "Project": {1: _fake_project()},
            "AILLMConfig": {1: _fake_config()},
        }
    )

    async def fake_generate(**kwargs):
        raise ValueError("API Key 解密失败")

    monkeypatch.setattr(ai_case_generation, "generate_case_drafts", fake_generate)

    body = AICaseGenerateIn(project_id=1, module_id=1)
    try:
        asyncio.run(ai_case_generation.generate_cases_endpoint(body=body, db=db, _=None))
    except Exception as exc:
        assert getattr(exc, "status_code", None) == 400
    else:
        raise AssertionError("应 400")
