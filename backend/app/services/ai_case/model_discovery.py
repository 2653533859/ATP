"""Discover chat-capable models from configured third-party providers."""

from __future__ import annotations

import re
from collections.abc import Iterator
from typing import Any
from urllib.parse import urlparse

import httpx

from app.services.ai_case.llm_client import _DEFAULT_ENDPOINTS

_DISCOVERY_TIMEOUT_SECONDS = 15.0
_NON_CHAT_MARKERS = (
    "embedding",
    "rerank",
    "moderation",
    "whisper",
    "tts",
    "text-to-speech",
)
_VISION_MARKERS = (
    "vision",
    "-vl",
    "_vl",
    "qwen-vl",
    "llava",
    "gemma3",
    "gpt-4o",
    "gpt-4.1",
    "claude-3",
    "claude-4",
)
_REASONING_MARKERS = (
    "reason",
    "thinking",
    "deepseek-r1",
    "qwen3",
    "o1",
    "o3",
    "o4",
)
# Model names may advertise the explicit absence of a capability (for example
# "grok-4.20-0309-non-reasoning"). Strip those fragments before substring matching so a
# negated name is not read as positive support.
_NEGATED_CAPABILITY_MARKERS = (
    "non-reasoning",
    "non_reasoning",
    "nonreasoning",
    "no-reasoning",
    "no_reasoning",
    "non-thinking",
    "non_thinking",
    "nonthinking",
    "no-thinking",
    "no_thinking",
    "non-vision",
    "non_vision",
    "nonvision",
    "no-vision",
    "no_vision",
)
_CAPABILITY_FIELDS = (
    "capabilities",
    "modalities",
    "input_modalities",
    "output_modalities",
    "supported_modalities",
)
_VISION_CAPABILITY_MARKERS = {"vision", "image", "images", "multimodal", "multimodal_input"}
_REASONING_CAPABILITY_MARKERS = {"reasoning", "thinking", "reasoning_effort", "chain_of_thought", "cot"}


def resolve_endpoint(provider: str, endpoint: str | None) -> str:
    base = (endpoint or _DEFAULT_ENDPOINTS.get(provider) or "").strip().rstrip("/")
    if not base:
        raise ValueError(f"未配置 endpoint 且 provider={provider} 无默认地址")
    parsed = urlparse(base)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        raise ValueError("endpoint 必须是完整的 http 或 https 地址")
    return base


def _openai_models_url(base: str) -> str:
    return f"{base}/models" if base.endswith("/v1") else f"{base}/v1/models"


def _ollama_tags_url(base: str) -> str:
    return f"{base}/tags" if base.endswith("/api") else f"{base}/api/tags"


def _headers(provider: str, api_key: str) -> dict[str, str]:
    if provider == "claude":
        return {
            "x-api-key": api_key,
            "anthropic-version": "2023-06-01",
            "Accept": "application/json",
        }
    headers = {"Accept": "application/json"}
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"
    return headers


def _capability_tokens(value: Any) -> Iterator[str]:
    """Yield normalized positive capability names from provider metadata."""
    if isinstance(value, dict):
        for key, item in value.items():
            if item is True:
                yield str(key)
            elif isinstance(item, (dict, list, tuple, set)):
                yield from _capability_tokens(item)
        return
    if isinstance(value, (list, tuple, set)):
        for item in value:
            yield from _capability_tokens(item)
        return
    if isinstance(value, str):
        normalized = value.strip().lower().replace("-", "_")
        if normalized:
            yield normalized
            yield from (part for part in re.split(r"[^a-z0-9_]+", normalized) if part)


def _provider_capabilities(raw: dict[str, Any] | None) -> tuple[set[str], bool]:
    if not isinstance(raw, dict):
        return set(), False
    tokens: set[str] = set()
    metadata_present = False
    for field in _CAPABILITY_FIELDS:
        if field not in raw:
            continue
        metadata_present = True
        tokens.update(_capability_tokens(raw[field]))
    return tokens, metadata_present


def _strip_negated_markers(lowered: str) -> str:
    """Remove explicit "no capability" fragments so they cannot match positive markers."""
    for marker in _NEGATED_CAPABILITY_MARKERS:
        lowered = lowered.replace(marker, "")
    return lowered


def _capability_hint(model_id: str, provider: str, raw: dict[str, Any] | None = None) -> dict[str, Any]:
    lowered = model_id.lower()
    provider_capabilities, provider_metadata_present = _provider_capabilities(raw)
    if provider_metadata_present:
        supports_vision: bool | None = True if provider_capabilities & _VISION_CAPABILITY_MARKERS else None
        supports_reasoning: bool | None = True if provider_capabilities & _REASONING_CAPABILITY_MARKERS else None
        capability_source = "provider"
    else:
        hinted = _strip_negated_markers(lowered)
        supports_vision = True if any(marker in hinted for marker in _VISION_MARKERS) else None
        supports_reasoning = True if any(marker in hinted for marker in _REASONING_MARKERS) else None
        capability_source = "model-name-hint"
    hints: list[str] = []
    if supports_vision is True:
        hints.append("vision")
    if supports_reasoning is True:
        hints.append("reasoning")
    return {
        "supports_vision": supports_vision,
        "supports_reasoning": supports_reasoning,
        "capability_source": capability_source,
        "capabilities": hints,
    }


def _model_option(item: dict[str, Any], provider: str) -> dict[str, Any] | None:
    model_id = str(item.get("id") or item.get("name") or item.get("model") or "").strip()
    if not model_id:
        return None
    return {
        "id": model_id,
        "label": str(item.get("display_name") or item.get("name") or model_id),
        "owned_by": item.get("owned_by") if isinstance(item.get("owned_by"), str) else None,
        **_capability_hint(model_id, provider, item),
    }


def _extract_options(payload: Any, provider: str) -> list[dict[str, Any]]:
    if isinstance(payload, dict):
        raw_models = payload.get("data")
        if not isinstance(raw_models, list):
            raw_models = payload.get("models")
    else:
        raw_models = payload
    if not isinstance(raw_models, list):
        raise ValueError("供应商返回的模型列表格式无法识别")

    options = [
        option for item in raw_models if isinstance(item, dict) for option in [_model_option(item, provider)] if option
    ]
    usable = [option for option in options if not any(marker in option["id"].lower() for marker in _NON_CHAT_MARKERS)]
    return sorted(usable or options, key=lambda item: item["id"].lower())


async def discover_models(provider: str, endpoint: str | None, api_key: str) -> list[dict[str, Any]]:
    base = resolve_endpoint(provider, endpoint)
    headers = _headers(provider, api_key)
    async with httpx.AsyncClient(timeout=_DISCOVERY_TIMEOUT_SECONDS, follow_redirects=False) as client:
        if provider == "ollama" and not base.endswith("/v1"):
            response = await client.get(_ollama_tags_url(base), headers=headers)
            if response.status_code == 404:
                response = await client.get(_openai_models_url(base), headers=headers)
        else:
            response = await client.get(_openai_models_url(base), headers=headers)
        response.raise_for_status()
        return _extract_options(response.json(), provider)
