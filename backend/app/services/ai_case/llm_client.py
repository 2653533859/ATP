"""LLM 调用客户端，统一 prompt → text 接口。

支持五种 provider:
  - deepseek / openai / qwen / ollama → OpenAI-compatible chat/completions
  - claude → Anthropic /v1/messages

均通过 httpx 直接发起 HTTP 请求，避免引入 SDK。
"""
from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any

import httpx

logger = logging.getLogger(__name__)


_DEFAULT_ENDPOINTS = {
    "deepseek": "https://api.deepseek.com",
    "openai": "https://api.openai.com",
    "qwen": "https://dashscope.aliyuncs.com/compatible-mode",
    "ollama": "http://localhost:11434",
    "claude": "https://api.anthropic.com",
}


@dataclass
class LLMRequest:
    provider: str
    api_key: str
    model_name: str
    prompt: str
    endpoint: str | None = None
    temperature: float = 0.4
    max_tokens: int = 2048
    system_prompt: str | None = None
    timeout_seconds: float = 60.0
    extra_params: dict | None = None
    image_base64: str | None = None
    image_media_type: str = "image/png"


@dataclass
class LLMResponse:
    text: str
    raw: dict


def _resolve_endpoint(provider: str, endpoint: str | None) -> str:
    base = endpoint or _DEFAULT_ENDPOINTS.get(provider)
    if not base:
        raise ValueError(f"未配置 endpoint 且 provider={provider} 无默认值")
    return base.rstrip("/")


async def _call_openai_compatible(request: LLMRequest) -> LLMResponse:
    base = _resolve_endpoint(request.provider, request.endpoint)
    url = f"{base}/v1/chat/completions"
    messages: list[dict] = []
    if request.system_prompt:
        messages.append({"role": "system", "content": request.system_prompt})
    if request.image_base64:
        messages.append(
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": request.prompt},
                    {
                        "type": "image_url",
                        "image_url": {
                            "url": f"data:{request.image_media_type};base64,{request.image_base64}"
                        },
                    },
                ],
            }
        )
    else:
        messages.append({"role": "user", "content": request.prompt})

    payload: dict[str, Any] = {
        "model": request.model_name,
        "messages": messages,
        "temperature": request.temperature,
        "max_tokens": request.max_tokens,
    }
    if request.extra_params:
        payload.update(request.extra_params)

    headers = {
        "Authorization": f"Bearer {request.api_key}",
        "Content-Type": "application/json",
    }

    async with httpx.AsyncClient(timeout=request.timeout_seconds) as client:
        resp = await client.post(url, json=payload, headers=headers)
        resp.raise_for_status()
        data = resp.json()

    try:
        text = data["choices"][0]["message"]["content"]
    except (KeyError, IndexError, TypeError) as exc:
        raise ValueError(f"LLM 返回结构无效: {data}") from exc
    return LLMResponse(text=text or "", raw=data)


async def _call_claude(request: LLMRequest) -> LLMResponse:
    base = _resolve_endpoint(request.provider, request.endpoint)
    url = f"{base}/v1/messages"

    payload: dict[str, Any] = {
        "model": request.model_name,
        "max_tokens": request.max_tokens,
        "temperature": request.temperature,
        "messages": [
            {
                "role": "user",
                "content": (
                    [
                        {
                            "type": "image",
                            "source": {
                                "type": "base64",
                                "media_type": request.image_media_type,
                                "data": request.image_base64,
                            },
                        },
                        {"type": "text", "text": request.prompt},
                    ]
                    if request.image_base64
                    else request.prompt
                ),
            }
        ],
    }
    if request.system_prompt:
        payload["system"] = request.system_prompt
    if request.extra_params:
        payload.update(request.extra_params)

    headers = {
        "x-api-key": request.api_key,
        "anthropic-version": "2023-06-01",
        "Content-Type": "application/json",
    }

    async with httpx.AsyncClient(timeout=request.timeout_seconds) as client:
        resp = await client.post(url, json=payload, headers=headers)
        resp.raise_for_status()
        data = resp.json()

    blocks = data.get("content") or []
    text_parts = [b.get("text", "") for b in blocks if isinstance(b, dict) and b.get("type") == "text"]
    return LLMResponse(text="".join(text_parts), raw=data)


async def call_llm(request: LLMRequest) -> LLMResponse:
    """统一入口：根据 provider 路由到具体适配器。"""
    provider = request.provider.lower()
    if provider == "claude":
        return await _call_claude(request)
    if provider in ("deepseek", "openai", "qwen", "ollama"):
        return await _call_openai_compatible(request)
    raise ValueError(f"不支持的 provider: {provider}")
