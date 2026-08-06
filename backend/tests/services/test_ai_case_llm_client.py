"""Tests for app.services.ai_case.llm_client + prompts."""

import asyncio
import sys
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from app.services.ai_case.llm_client import LLMRequest, call_llm
from app.services.ai_case.prompts import build_user_prompt, parse_llm_json_array


# ──────────── prompts ────────────


def test_build_user_prompt_contains_constraints():
    prompt = build_user_prompt(
        endpoints=[{"method": "GET", "path": "/x", "summary": "S"}],
        user_requirement="登录场景",
        case_type="api",
        priority="P1",
        case_level="core",
        max_cases=3,
    )
    assert "P1" in prompt and "core" in prompt and "api" in prompt
    assert "GET /x" in prompt
    assert "登录场景" in prompt
    assert "3 条测试用例" in prompt


def test_build_user_prompt_empty_endpoints():
    prompt = build_user_prompt(
        endpoints=[],
        user_requirement="",
        case_type="api",
        priority="P2",
        case_level="regression",
        max_cases=1,
    )
    assert "未提供接口" in prompt


def test_parse_llm_json_array_plain():
    text = '[{"name": "a"}, {"name": "b"}]'
    assert parse_llm_json_array(text) == [{"name": "a"}, {"name": "b"}]


def test_parse_llm_json_array_with_fence():
    text = """```json
[{"name": "a"}]
```"""
    assert parse_llm_json_array(text) == [{"name": "a"}]


def test_parse_llm_json_array_with_prefix_text():
    text = '说明文字...\n[{"x": 1}]\n收尾'
    assert parse_llm_json_array(text) == [{"x": 1}]


def test_parse_llm_json_array_missing_bracket_raises():
    with pytest.raises(ValueError):
        parse_llm_json_array("not json")


def test_parse_llm_json_array_not_array():
    with pytest.raises(ValueError):
        parse_llm_json_array('{"name": "a"}')


# ──────────── llm_client ────────────


class _FakeResponse:
    def __init__(self, payload):
        self._payload = payload

    def json(self):
        return self._payload

    def raise_for_status(self):
        return None


class _FakeAsyncClient:
    def __init__(self, response):
        self._response = response
        self.captured: dict = {}

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        return None

    async def post(self, url, json=None, headers=None):
        self.captured = {"url": url, "json": json, "headers": headers}
        return self._response


def _patch_httpx(monkeypatch, response_payload):
    response = _FakeResponse(response_payload)
    fake_client = _FakeAsyncClient(response)

    def factory(*args, **kwargs):
        return fake_client

    monkeypatch.setattr("app.services.ai_case.llm_client.httpx.AsyncClient", factory)
    return fake_client


def test_call_llm_openai_compatible(monkeypatch):
    payload = {
        "choices": [{"message": {"content": "hello"}}],
    }
    captured = _patch_httpx(monkeypatch, payload)

    request = LLMRequest(
        provider="deepseek",
        api_key="sk-xxx",
        model_name="deepseek-chat",
        prompt="hi",
        system_prompt="sys",
    )
    response = asyncio.run(call_llm(request))
    assert response.text == "hello"
    assert captured.captured["url"].endswith("/v1/chat/completions")
    assert captured.captured["headers"]["Authorization"] == "Bearer sk-xxx"
    body = captured.captured["json"]
    assert body["model"] == "deepseek-chat"
    assert body["messages"][0]["role"] == "system"
    assert body["messages"][1]["content"] == "hi"


def test_call_llm_claude(monkeypatch):
    payload = {
        "content": [
            {"type": "text", "text": "claude says"},
            {"type": "text", "text": "!"},
        ]
    }
    captured = _patch_httpx(monkeypatch, payload)

    request = LLMRequest(
        provider="claude",
        api_key="sk-ant",
        model_name="claude-3-5-sonnet",
        prompt="hi",
        system_prompt="sys",
    )
    response = asyncio.run(call_llm(request))
    assert response.text == "claude says!"
    assert captured.captured["url"].endswith("/v1/messages")
    assert captured.captured["headers"]["x-api-key"] == "sk-ant"
    body = captured.captured["json"]
    assert body["model"] == "claude-3-5-sonnet"
    assert body["system"] == "sys"


def test_call_llm_invalid_provider():
    request = LLMRequest(provider="foo", api_key="x", model_name="m", prompt="p")
    with pytest.raises(ValueError):
        asyncio.run(call_llm(request))


def test_call_llm_openai_invalid_response(monkeypatch):
    _patch_httpx(monkeypatch, {"unexpected": True})
    request = LLMRequest(provider="openai", api_key="x", model_name="m", prompt="p")
    with pytest.raises(ValueError):
        asyncio.run(call_llm(request))


def test_call_llm_custom_endpoint(monkeypatch):
    payload = {"choices": [{"message": {"content": "x"}}]}
    captured = _patch_httpx(monkeypatch, payload)

    request = LLMRequest(
        provider="ollama",
        api_key="ignored",
        model_name="qwen2",
        prompt="p",
        endpoint="http://my-host:8000",
    )
    asyncio.run(call_llm(request))
    assert captured.captured["url"] == "http://my-host:8000/v1/chat/completions"


def test_call_llm_custom_v1_endpoint_does_not_duplicate_prefix(monkeypatch):
    payload = {"choices": [{"message": {"content": "x"}}]}
    captured = _patch_httpx(monkeypatch, payload)

    request = LLMRequest(
        provider="openai",
        api_key="token",
        model_name="local-model",
        prompt="p",
        endpoint="http://my-host:3000/v1",
    )
    asyncio.run(call_llm(request))
    assert captured.captured["url"] == "http://my-host:3000/v1/chat/completions"
