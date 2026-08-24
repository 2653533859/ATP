"""Shared helpers for synchronizing internal defects with external issues."""

from __future__ import annotations

import re
from typing import Any


def map_external_status(status: str | None) -> str | None:
    """Map common Jira/ZenTao/GitHub/GitLab statuses to internal defect states."""
    if not status:
        return None
    normalized = " ".join(str(status).strip().lower().replace("_", " ").replace("-", " ").split())
    if normalized in {"closed", "close", "cancelled", "canceled", "cancel"}:
        return "closed"
    if normalized in {"resolved", "resolve", "done", "completed", "fixed", "verified"}:
        return "resolved"
    if normalized in {"reopened", "reopen"}:
        return "reopened"
    if normalized in {"in progress", "in development", "developing", "fixing", "assigned", "active", "doing"}:
        return "in_progress"
    if normalized in {"open", "new", "to do", "todo", "confirmed", "pending", "待处理", "未开始"}:
        return "open"
    return None


def build_external_defect_description(defect: Any) -> str:
    """Build a compact, non-sensitive issue body from an internal defect."""
    lines = [
        "由 ATP 内部缺陷同步创建。",
        f"内部缺陷：#{defect.id}",
        f"优先级：{defect.priority}",
        f"严重程度：{defect.severity}",
        "",
        _redact_text(defect.description or "（无描述）"),
    ]
    if defect.labels:
        lines.extend(["", f"标签：{', '.join(str(label) for label in defect.labels[:20])}"])
    return "\n".join(lines)[:20_000]


EXTERNAL_SYNC_ERROR = "外部 Issue 同步失败，请检查集成配置和 Issue 权限"

_SECRET_PATTERN = re.compile(
    r"(?i)(authorization|cookie|set-cookie|password|passwd|token|secret|api[_-]?key)\s*[:=]\s*(?:bearer\s+)?[^,;\n]+"
)
_SECRET_FIELD_PATTERN = re.compile(
    r"(?i)([\"']?(?:authorization|cookie|set-cookie|password|passwd|token|secret|api[_-]?key)[\"']?\s*[:=]\s*[\"']?)([^\"',;\s}\]]+)"
)


def _redact_text(value: Any, limit: int = 20_000) -> str:
    text = str(value or "")
    text = _SECRET_PATTERN.sub(lambda match: f"{match.group(1)}=[REDACTED]", text)
    return _SECRET_FIELD_PATTERN.sub(lambda match: f"{match.group(1)}[REDACTED]", text)[:limit]
