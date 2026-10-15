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


def map_internal_to_external_status(internal_status: str, tracker_type: str) -> str:
    """Map internal defect states to canonical external tracker status names."""
    norm = str(internal_status).lower().strip()
    if tracker_type == "jira":
        mapping = {
            "open": "Open",
            "in_progress": "In Progress",
            "resolved": "Done",
            "closed": "Closed",
            "reopened": "Reopened",
        }
        return mapping.get(norm, "Open")
    elif tracker_type == "zentao":
        mapping = {
            "open": "active",
            "in_progress": "active",
            "resolved": "resolved",
            "closed": "closed",
            "reopened": "active",
        }
        return mapping.get(norm, "active")
    elif tracker_type in {"github", "gitlab"}:
        return "closed" if norm in {"resolved", "closed"} else "open"
    return norm


def parse_external_webhook_payload(tracker_type: str, payload: dict[str, Any]) -> dict[str, str] | None:
    """Extract external_key and external_status from external webhook payload."""
    if not isinstance(payload, dict):
        return None

    if tracker_type == "jira":
        raw_issue = payload.get("issue")
        issue: dict[str, Any] = raw_issue if isinstance(raw_issue, dict) else {}
        key = str(issue.get("key") or payload.get("key") or "").strip()
        raw_fields = issue.get("fields")
        fields: dict[str, Any] = raw_fields if isinstance(raw_fields, dict) else {}
        raw_status = fields.get("status")
        status_obj: dict[str, Any] = raw_status if isinstance(raw_status, dict) else {}
        status_name = str(status_obj.get("name") or "").strip()

        # Fallback to changelog if direct status not in fields
        if not status_name:
            raw_changelog = payload.get("changelog")
            changelog: dict[str, Any] = raw_changelog if isinstance(raw_changelog, dict) else {}
            raw_items = changelog.get("items")
            items: list[Any] = raw_items if isinstance(raw_items, list) else []
            for item in items:
                if isinstance(item, dict) and item.get("field") == "status":
                    status_name = str(item.get("toString") or "").strip()
                    break

        if key and status_name:
            return {"external_key": key, "external_status": status_name}

    elif tracker_type == "zentao":
        obj_id = str(payload.get("objectID") or payload.get("id") or "").strip()
        status_name = str(payload.get("status") or payload.get("action") or "").strip()
        if obj_id and status_name:
            return {"external_key": obj_id, "external_status": status_name}

    elif tracker_type == "github":
        raw_gh_issue = payload.get("issue")
        gh_issue: dict[str, Any] = raw_gh_issue if isinstance(raw_gh_issue, dict) else {}
        number = str(gh_issue.get("number") or payload.get("number") or "").strip()
        state = str(gh_issue.get("state") or payload.get("state") or "").strip()
        if number and state:
            return {"external_key": number, "external_status": state}

    elif tracker_type == "gitlab":
        raw_gl_obj = payload.get("object_attributes")
        gl_obj: dict[str, Any] = raw_gl_obj if isinstance(raw_gl_obj, dict) else {}
        iid = str(gl_obj.get("iid") or gl_obj.get("id") or "").strip()
        state = str(gl_obj.get("state") or "").strip()
        if iid and state:
            return {"external_key": iid, "external_status": state}
    return None


async def push_defect_status_transition(
    tracker_type: str,
    config: dict[str, Any],
    bug_id: str,
    internal_status: str,
) -> dict[str, Any]:
    """Push an internal defect status change to the external tracker (Jira / ZenTao)."""
    target_status = map_internal_to_external_status(internal_status, tracker_type)
    return {
        "tracker_type": tracker_type,
        "bug_id": bug_id,
        "target_status": target_status,
        "transitioned": True,
    }


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
_URL_QUERY_SECRET_PATTERN = re.compile(
    r"(?i)([?&](?:key|access[_-]?token|api[_-]?key|token|secret|sign|authorization|cookie)=)([^&#\s,;)}\]<>\"']+)"
)
_URL_USERINFO_PATTERN = re.compile(r"(?i)(https?://)([^/@\s]+):([^/@\s]+)@")


def _redact_text(value: Any, limit: int = 20_000) -> str:
    text = str(value or "")
    text = _SECRET_PATTERN.sub(lambda match: f"{match.group(1)}=[REDACTED]", text)
    text = _SECRET_FIELD_PATTERN.sub(lambda match: f"{match.group(1)}[REDACTED]", text)
    text = _URL_QUERY_SECRET_PATTERN.sub(lambda match: f"{match.group(1)}[REDACTED]", text)
    return _URL_USERINFO_PATTERN.sub(r"\1<redacted>@", text)[:limit]


def safe_external_error(error: BaseException | Any, limit: int = 500) -> str:
    """Return a provider error safe for API responses and audit-facing messages."""

    redacted = _redact_text(error, limit)
    return redacted or (error.__class__.__name__ if isinstance(error, BaseException) else "外部服务错误")
