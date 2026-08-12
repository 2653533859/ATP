"""Tests for third-party LLM model discovery."""

import asyncio

from app.services.ai_case import model_discovery


class _Response:
    def __init__(self, payload, status_code=200):
        self._payload = payload
        self.status_code = status_code

    def json(self):
        return self._payload

    def raise_for_status(self):
        return None


class _AsyncClient:
    requests: list[tuple[str, dict[str, str]]] = []
    response = _Response({"data": []})

    def __init__(self, **_kwargs):
        pass

    async def __aenter__(self):
        return self

    async def __aexit__(self, *_args):
        return None

    async def get(self, url, headers):
        self.requests.append((url, headers))
        return self.response


def test_openai_compatible_discovery_filters_non_chat_models(monkeypatch):
    _AsyncClient.requests = []
    _AsyncClient.response = _Response(
        {
            "data": [
                {"id": "text-embedding-3-small", "owned_by": "openai"},
                {"id": "qwen-vl-max", "owned_by": "qwen"},
                {"id": "deepseek-r1", "owned_by": "deepseek"},
            ]
        }
    )
    monkeypatch.setattr(model_discovery.httpx, "AsyncClient", _AsyncClient)

    models = asyncio.run(model_discovery.discover_models("openai", "https://llm.example.com/v1", "secret-key"))

    assert [model["id"] for model in models] == ["deepseek-r1", "qwen-vl-max"]
    assert models[0]["supports_reasoning"] is True
    assert models[1]["supports_vision"] is True
    assert _AsyncClient.requests == [
        (
            "https://llm.example.com/v1/models",
            {"Accept": "application/json", "Authorization": "Bearer secret-key"},
        )
    ]


def test_ollama_discovery_uses_native_tags_endpoint(monkeypatch):
    _AsyncClient.requests = []
    _AsyncClient.response = _Response(
        {
            "models": [
                {"name": "llama3.2:latest", "details": {"family": "llama"}},
                {"name": "llava:latest", "capabilities": ["completion", "vision"]},
            ]
        }
    )
    monkeypatch.setattr(model_discovery.httpx, "AsyncClient", _AsyncClient)

    models = asyncio.run(model_discovery.discover_models("ollama", "http://127.0.0.1:11434", ""))

    assert [model["id"] for model in models] == ["llama3.2:latest", "llava:latest"]
    assert models[1]["supports_vision"] is True
    assert _AsyncClient.requests[0] == (
        "http://127.0.0.1:11434/api/tags",
        {"Accept": "application/json"},
    )


def test_openai_compatible_discovery_uses_custom_v1_endpoint(monkeypatch):
    _AsyncClient.requests = []
    _AsyncClient.response = _Response({"data": [{"id": "qwen2.5-vl", "owned_by": "third-party"}]})
    monkeypatch.setattr(model_discovery.httpx, "AsyncClient", _AsyncClient)

    models = asyncio.run(
        model_discovery.discover_models("openai_compatible", "https://llm.example.com/v1", "service-token")
    )

    assert [model["id"] for model in models] == ["qwen2.5-vl"]
    assert _AsyncClient.requests == [
        (
            "https://llm.example.com/v1/models",
            {"Accept": "application/json", "Authorization": "Bearer service-token"},
        )
    ]
