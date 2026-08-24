"""Shared redaction and ranking helpers for knowledge search."""

from __future__ import annotations

import re
from typing import Any


_SENSITIVE_TEXT = re.compile(
    r"(?i)(authorization|cookie|set-cookie|password|passwd|token|secret|api[_-]?key|access[_-]?key|refresh[_-]?token|credential)"
    r"\s*[:=]\s*(?:bearer\s+)?[^,;\s\n]+"
)
_URL_QUERY_SECRET = re.compile(
    r"(?i)([?&](?:token|secret|password|passwd|api[_-]?key|access[_-]?key|signature)=)[^&#\s]+"
)
_URL_USERINFO = re.compile(r"(?i)(https?://)[^/@\s:]+:[^/@\s]+@")


def redact_knowledge_text(value: str | None, *, limit: int = 50_000) -> str | None:
    """Mask credentials in free text before it is stored or returned."""
    if value is None:
        return None
    redacted = _SENSITIVE_TEXT.sub(lambda match: f"{match.group(1)}=[已脱敏]", str(value))
    redacted = _URL_QUERY_SECRET.sub(r"\1[已脱敏]", redacted)
    redacted = _URL_USERINFO.sub(r"\1[已脱敏]@", redacted)
    return redacted[:limit]


def redact_knowledge_value(value: Any, *, limit: int = 8_000) -> str:
    """Serialize small structured source data through the same text redactor."""
    if isinstance(value, str):
        text = value
    else:
        import json

        text = json.dumps(value, ensure_ascii=False, default=str)
    return redact_knowledge_text(text, limit=limit) or ""


def redact_knowledge_tags(values: list[str] | None) -> list[str]:
    """Keep tags useful for filtering without allowing credential leakage."""
    safe_values = [redact_knowledge_text(value, limit=128) for value in values or []]
    return list(dict.fromkeys(value for value in safe_values if value))[:20]


def search_terms(query: str | None) -> list[str]:
    if not query or not query.strip():
        return []
    raw = query.strip().lower()
    terms = re.findall(r"[\u4e00-\u9fff]{2,20}|[a-z0-9_./:-]{2,}", raw, flags=re.IGNORECASE)
    terms.append(raw)
    return list(dict.fromkeys(term for term in terms if term))[:12]


def score_text(query: str | None, title: str, body: str, tags: list[str] | None = None) -> tuple[int, list[str]]:
    terms = search_terms(query)
    if not terms:
        return 0, []
    normalized_title = title.lower()
    normalized_body = body.lower()
    normalized_tags = " ".join(tags or []).lower()
    score = 0
    matched: list[str] = []
    for term in terms:
        if term in normalized_title:
            score += 12
            matched.append(term)
        elif term in normalized_body:
            score += 5
            matched.append(term)
        elif term in normalized_tags:
            score += 7
            matched.append(term)
    if query and query.strip().lower() in normalized_title:
        score += 8
    return score, list(dict.fromkeys(matched))[:6]


def make_excerpt(text: str, query: str | None, *, limit: int = 420) -> str:
    safe_text = redact_knowledge_text(text, limit=50_000) or ""
    compact = " ".join(safe_text.split())
    if len(compact) <= limit:
        return compact
    terms = search_terms(query)
    position = next((compact.lower().find(term) for term in terms if compact.lower().find(term) >= 0), 0)
    start = max(0, position - limit // 3)
    excerpt = compact[start : start + limit]
    return ("…" if start else "") + excerpt + ("…" if start + limit < len(compact) else "")
