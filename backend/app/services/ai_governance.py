"""Helpers for model, prompt, limit, and fallback governance.

AILLMConfig.default_params remains the single editable JSON surface. These
helpers read reserved governance keys from it and keep provider extra params
separate from platform controls.
"""

from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from typing import Any

from app.models.ai_llm_config import AILLMConfig

_ALLOWED_LLM_EXTRA_PARAMS = {
    "frequency_penalty",
    "enable_thinking",
    "max_tokens",
    "presence_penalty",
    "reasoning_effort",
    "response_format",
    "seed",
    "temperature",
    "thinking",
    "top_p",
}

_SENSITIVE_TEXT_RE = re.compile(
    r"(?i)(?P<key>access[_-]?token|api[_-]?key|token|secret|password|passwd|sign(?:ature)?|authorization|cookie)"
    r"(?P<sep>\s*[:=]\s*)(?P<value>[^&\s,;)}\]<>\"']+)"
)
_SENSITIVE_JSON_FIELD_RE = re.compile(
    r'(?i)(?P<quote>["\'])(?P<key>access[_-]?token|api[_-]?key|token|secret|password|passwd|'
    r"sign(?:ature)?|authorization|cookie)(?P=quote)(?P<sep>\s*:\s*)"
    r'(?P<value_quote>["\'])(?P<value>.*?)(?P=value_quote)'
)
_SENSITIVE_QUOTED_VALUE_RE = re.compile(
    r"(?i)(?P<key>access[_-]?token|api[_-]?key|token|secret|password|passwd|"
    r"sign(?:ature)?|authorization|cookie)(?P<sep>\s*[:=]\s*)"
    r'(?P<value_quote>["\'])(?P<value>.*?)(?P=value_quote)'
)
_URL_QUERY_SECRET_RE = re.compile(
    r"(?i)(?P<prefix>[?&](?:key|access[_-]?token|api[_-]?key|token|secret|sign(?:ature)?|authorization|cookie)"
    r"\s*=\s*)(?P<value>[^&#\s,;)}\]<>\"']+)"
)
_URL_USERINFO_RE = re.compile(r"(?i)(https?://)([^/@\s]+):([^/@\s]+)@")


def redact_llm_text(value: object, *, limit: int = 12_000) -> str:
    """Return bounded LLM text safe to expose in an API response.

    JSON responses are redacted by field name first, while plain-text responses
    use conservative key/value and URL credential patterns. Provider response
    bodies are untrusted input and must never be returned verbatim.
    """

    normalized = ("" if value is None else str(value)).replace("\r", " ").replace("\n", " ").replace("\x00", " ")
    try:
        from app.services.ai_case.context import redact_context

        parsed = json.loads(normalized)
        safe = json.dumps(redact_context(parsed), ensure_ascii=False, separators=(",", ":"))
    except (TypeError, ValueError):
        safe = normalized
    safe = _SENSITIVE_JSON_FIELD_RE.sub(
        lambda match: (
            f"{match.group('quote')}{match.group('key')}{match.group('quote')}"
            f"{match.group('sep')}{match.group('value_quote')}[已脱敏]{match.group('value_quote')}"
        ),
        safe,
    )
    safe = _SENSITIVE_QUOTED_VALUE_RE.sub(
        lambda match: (
            f"{match.group('key')}{match.group('sep')}{match.group('value_quote')}"
            f"[已脱敏]{match.group('value_quote')}"
        ),
        safe,
    )
    safe = _SENSITIVE_TEXT_RE.sub(r"\g<key>\g<sep>***", safe)
    safe = _URL_QUERY_SECRET_RE.sub(r"\g<prefix><redacted>", safe)
    safe = _URL_USERINFO_RE.sub(r"\1<redacted>@", safe)
    return safe[:limit]


def _params(config: AILLMConfig | None) -> dict[str, Any]:
    if config is None or not isinstance(config.default_params, dict):
        return {}
    return dict(config.default_params)


def llm_extra_params_from_values(values: Any) -> dict[str, Any] | None:
    """Filter provider parameters from a config or unsaved health-check payload."""
    source = values if isinstance(values, dict) else {}
    params = {key: value for key, value in source.items() if key in _ALLOWED_LLM_EXTRA_PARAMS}
    return params or None


def llm_extra_params(config: AILLMConfig | None) -> dict[str, Any] | None:
    """Return provider params after removing ATP governance keys."""
    return llm_extra_params_from_values(_params(config))


def resolve_system_prompt(config: AILLMConfig | None, capability: str, default_prompt: str) -> str:
    """Resolve a prompt template override for a capability.

    Supported shapes in default_params:
    - {"system_prompt": "..."} applies to all capabilities.
    - {"prompt_templates": {"ai_case_generation": "..."}}
    """
    params = _params(config)
    templates = params.get("prompt_templates")
    if isinstance(templates, dict):
        value = templates.get(capability)
        if isinstance(value, str) and value.strip():
            return value.strip()
    value = params.get("system_prompt")
    if isinstance(value, str) and value.strip():
        return value.strip()
    return default_prompt


def fallback_enabled(config: AILLMConfig | None, *, default: bool = True) -> bool:
    params = _params(config)
    value = params.get("fallback_enabled")
    return value if isinstance(value, bool) else default


def resolve_daily_limit(config: AILLMConfig | None, capability: str, global_default: int = 0) -> int:
    """Return a per-capability daily limit; 0 means unlimited."""
    params = _params(config)
    limits = params.get("daily_limits")
    value = limits.get(capability) if isinstance(limits, dict) else params.get("daily_limit")
    if value is None:
        return max(0, int(global_default or 0))
    try:
        number = int(value)
    except (TypeError, ValueError):
        return max(0, int(global_default or 0))
    return max(0, number)


async def check_and_incr_daily_limit(
    *,
    config: AILLMConfig | None,
    capability: str,
    global_default: int = 0,
) -> bool:
    """Best-effort daily quota check.

    Redis outages degrade to allowed so AI features do not fail closed during
    local development or transient infra incidents.
    """
    limit = resolve_daily_limit(config, capability, global_default)
    if limit <= 0:
        return True
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    config_id = getattr(config, "id", "global") or "global"
    key = f"ai_governance:daily:{capability}:{config_id}:{today}"
    try:
        from app.core.redis_client import close_async_redis, get_async_redis

        redis = get_async_redis()
        try:
            value = await redis.incr(key)
            if value == 1:
                await redis.expire(key, 60 * 60 * 36)
            return value <= limit
        finally:
            await close_async_redis(redis)
    except Exception:
        return True
