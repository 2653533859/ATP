"""Unified template variable & dynamic function rendering utilities."""

from __future__ import annotations

import re
import secrets
import string
import time
import uuid
from datetime import UTC, datetime
from typing import Any

_RNG = secrets.SystemRandom()
_ALPHANUM = string.ascii_letters + string.digits
_PLACEHOLDER_PATTERN = re.compile(r"\{\{([^{}]+?)\}\}")
_FUNC_PATTERN = re.compile(r"^(\$[a-zA-Z_][a-zA-Z0-9_]*)(?:\(([^()]*)\))?$")

_SAMPLE_NAMES = (
    "Alice Chen",
    "Bob Lin",
    "Carol Wang",
    "David Zhang",
    "Eve Liu",
    "Frank Zhou",
    "Grace Wu",
    "Henry Sun",
)
_PHONE_SECOND_DIGITS = "3456789"
_DEFAULT_RANDOM_INT_MAX = 999_999
_MAX_RANDOM_INT_BOUND = 10**12
_DEFAULT_RANDOM_STR_LEN = 8
_MAX_RANDOM_STR_LEN = 256


def _random_alnum(length: int) -> str:
    safe_len = max(1, min(length, _MAX_RANDOM_STR_LEN))
    return "".join(_RNG.choices(_ALPHANUM, k=safe_len))


def resolve_dynamic_variable(expr: str) -> Any | None:
    """Resolve a built-in dynamic expression (e.g. `$uuid`, `$random_int(1, 100)`).

    Returns ``None`` when ``expr`` is not a recognized dynamic variable.
    """
    cleaned = expr.strip()
    match = _FUNC_PATTERN.match(cleaned)
    if not match:
        return None

    name = match.group(1).lower()
    raw_args = match.group(2)
    args = [part.strip() for part in raw_args.split(",") if part.strip()] if raw_args is not None else []

    if name == "$uuid" and not args:
        return str(uuid.uuid4())
    if name == "$uuid_hex" and not args:
        return uuid.uuid4().hex
    if name == "$timestamp" and not args:
        return int(time.time())
    if name == "$timestamp_ms" and not args:
        return int(time.time() * 1000)
    if name == "$iso_now" and not args:
        return datetime.now(UTC).isoformat().replace("+00:00", "Z")
    if name == "$date" and not args:
        return datetime.now(UTC).strftime("%Y-%m-%d")
    if name == "$random_bool" and not args:
        return _RNG.choice((True, False))
    if name == "$random_name" and not args:
        return _RNG.choice(_SAMPLE_NAMES)
    if name == "$random_email" and not args:
        return f"user_{_random_alnum(_DEFAULT_RANDOM_STR_LEN).lower()}@example.com"
    if name == "$random_phone" and not args:
        second = _RNG.choice(_PHONE_SECOND_DIGITS)
        tail = "".join(_RNG.choices(string.digits, k=9))
        return f"1{second}{tail}"

    if name == "$random_int":
        if not args:
            return _RNG.randint(0, _DEFAULT_RANDOM_INT_MAX)
        if len(args) == 2:
            try:
                low = int(args[0])
                high = int(args[1])
            except ValueError:
                return None
            if abs(low) > _MAX_RANDOM_INT_BOUND or abs(high) > _MAX_RANDOM_INT_BOUND:
                return None
            if low > high:
                low, high = high, low
            return _RNG.randint(low, high)
        return None

    if name == "$random_str":
        if not args:
            return _random_alnum(_DEFAULT_RANDOM_STR_LEN)
        if len(args) == 1:
            try:
                length = int(args[0])
            except ValueError:
                return None
            return _random_alnum(length)
        return None

    return None


def _resolve_placeholder(expr: str, context: dict[str, Any] | None) -> tuple[bool, Any]:
    key = expr.strip()
    if context and key in context:
        return True, context[key]
    dynamic_val = resolve_dynamic_variable(key)
    if dynamic_val is not None:
        return True, dynamic_val
    return False, None


def render_template_string(template: str, context: dict[str, Any] | None = None) -> str:
    """Replace `{{var}}` and `{{$dynamic}}` placeholders in a string.

    Explicit `context` values take precedence over built-in dynamic variables.
    Unknown placeholders are left unchanged.
    """
    if not isinstance(template, str):
        template = str(template)
    if "{{" not in template:
        return template

    def _replace(match: re.Match[str]) -> str:
        found, resolved = _resolve_placeholder(match.group(1), context)
        if found:
            return str(resolved)
        return match.group(0)

    return _PLACEHOLDER_PATTERN.sub(_replace, template)


def render_template_value(
    value: Any,
    context: dict[str, Any] | None = None,
    *,
    preserve_type: bool = True,
) -> Any:
    """Recursively render placeholders across strings, lists, and dicts."""
    if isinstance(value, str):
        if preserve_type:
            stripped = value.strip()
            if stripped.startswith("{{") and stripped.endswith("}}") and stripped.count("{{") == 1:
                found, resolved = _resolve_placeholder(stripped[2:-2], context)
                if found:
                    return resolved
        return render_template_string(value, context)
    if isinstance(value, list):
        return [render_template_value(item, context, preserve_type=preserve_type) for item in value]
    if isinstance(value, dict):
        return {k: render_template_value(v, context, preserve_type=preserve_type) for k, v in value.items()}
    return value
