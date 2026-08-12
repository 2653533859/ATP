"""Build small, redacted project context for AI case generation."""

from __future__ import annotations

import json
import re
from typing import Any

from app.services.dataset_storage import rows_from_source


_SENSITIVE_KEY = re.compile(
    r"(?:password|passwd|secret|token|api[_-]?key|authorization|cookie|credential|private[_-]?key|access[_-]?key|refresh[_-]?token|session)",
    re.IGNORECASE,
)
_MAX_TEXT_LENGTH = 4000
_MAX_DATASET_SAMPLES = 5
_MAX_RECORDED_SAMPLES = 3


def _is_sensitive_key(key: object) -> bool:
    return bool(_SENSITIVE_KEY.search(str(key)))


def redact_context(value: Any, *, key: object | None = None) -> Any:
    """Redact secret-looking fields before project data is sent to an LLM."""
    if key is not None and _is_sensitive_key(key):
        return "[已脱敏]"
    if isinstance(value, dict):
        return {str(item_key): redact_context(item_value, key=item_key) for item_key, item_value in value.items()}
    if isinstance(value, list):
        return [redact_context(item) for item in value]
    if isinstance(value, tuple):
        return [redact_context(item) for item in value]
    if isinstance(value, str) and len(value) > _MAX_TEXT_LENGTH:
        return f"{value[:_MAX_TEXT_LENGTH]}…"
    return value


def build_dataset_context(dataset: Any, *, snapshot: Any | None = None) -> dict[str, Any]:
    """Expose a dataset or immutable snapshot without sending the full dataset to the LLM."""
    source = snapshot or dataset
    schema_fields = []
    for field in getattr(source, "schema_fields", None) or []:
        if not isinstance(field, dict) or not field.get("name"):
            continue
        schema_fields.append(
            {
                "name": str(field["name"]),
                "type": field.get("type", "string"),
                "required": bool(field.get("required", False)),
                "default": redact_context(field.get("default"), key=field.get("name")),
            }
        )
    source_rows = rows_from_source(source)
    rows = [redact_context(row) for row in source_rows[:_MAX_DATASET_SAMPLES]]
    context = {
        "id": dataset.id,
        "name": dataset.name,
        "description": dataset.description,
        "format": source.format,
        "validation_policy": getattr(source, "validation_policy", "soft") or "soft",
        "row_count": len(source_rows),
        "schema_fields": schema_fields,
        "sample_rows": rows,
    }
    if snapshot is not None:
        context["version"] = snapshot.version
    return context


def _response_context(value: Any) -> Any:
    if not isinstance(value, str):
        return redact_context(value)
    try:
        return redact_context(json.loads(value))
    except (TypeError, ValueError):
        return redact_context(value)


def build_mock_rule_context(rule: Any) -> dict[str, Any]:
    """Expose the mock contract while omitting ownership and audit metadata."""
    return {
        "id": rule.id,
        "name": rule.name,
        "method": rule.method.value if hasattr(rule.method, "value") else str(rule.method),
        "path": rule.path,
        "status_code": rule.status_code,
        "response_headers": redact_context(rule.response_headers or {}),
        "response_body": _response_context(rule.response_body),
        "match_conditions": redact_context(rule.match_conditions or {}),
        "delay_ms": rule.delay_ms,
        "recorded_samples": redact_context((rule.recorded_samples or [])[:_MAX_RECORDED_SAMPLES]),
    }
