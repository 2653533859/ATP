"""Whitelist outbound sanitizer and dynamic-field guards for AI assertion & diagnosis."""

from __future__ import annotations

import base64
import re
from typing import Any
from urllib.parse import quote

IDENTIFIER_SECRET_MIN = 4
DEFAULT_MAX_SCHEMA_NODES = 250
DEFAULT_MAX_SCHEMA_DEPTH = 12

SENSITIVE_KEY_RE = re.compile(
    r"token|secret|password|passwd|authorization|cookie|api.?key|credential|session|"
    r"email|phone|mobile|id_?card|身份证|姓名|密码|密钥|手机号|邮箱|address|"
    r"real.?name|full.?name|user.?name|nick.?name|first.?name|last.?name|^name$",
    re.I,
)

DYNAMIC_FIELD_RE = re.compile(
    r"(?:^|[._-])(?:id|uuid|guid|token|jwt|nonce|timestamp|ts|created.?at|updated.?at|"
    r"expire|expires.?at|trace.?id|request.?id|session.?id|order.?no|trade.?no|time|date)$|"
    r"(?:Id|ID|Uuid|UUID|Token|Timestamp|No)$|编号|时间",
)

BUSINESS_RESULT_FIELD_RE = re.compile(
    r"^(code|success|status|result|ok|message|msg|errcode|errmsg|error_?code|error_?msg)$",
    re.I,
)

_PERSONAL_RE = re.compile(
    r"[\w.+-]+@[\w.-]+\.[A-Za-z]{2,}|"
    r"(?<!\d)(?:\+?86[ -]?)?1[3-9]\d{9}(?!\d)|"
    r"(?<!\d)\d{17}[\dXx](?!\d)|"
    r"(?i:bearer|basic)\s+[A-Za-z0-9._+/=\-]+",
)


def json_value_type(value: Any) -> str:
    if value is None:
        return "null"
    if isinstance(value, bool):
        return "boolean"
    if isinstance(value, (int, float)):
        return "number"
    if isinstance(value, dict):
        return "object"
    if isinstance(value, list):
        return "array"
    return "string"


def is_dynamic_field_path(expression: str) -> bool:
    """Return True if the terminal segment of a JSONPath looks like a dynamic per-run value."""
    expr = str(expression or "").strip()
    if not expr or expr == "$":
        return False
    cleaned = re.sub(r"\[\d+\]$", "", expr)
    leaf = cleaned.rsplit(".", 1)[-1].lstrip("$")
    if not leaf:
        return False
    return bool(DYNAMIC_FIELD_RE.search(leaf))


def is_business_result_path(expression: str) -> bool:
    """Return True if the JSONPath refers to a top-level or nested business status indicator."""
    expr = str(expression or "").strip()
    if not expr or expr == "$":
        return False
    cleaned = re.sub(r"\[\d+\]$", "", expr)
    leaf = cleaned.rsplit(".", 1)[-1].lstrip("$")
    return bool(BUSINESS_RESULT_FIELD_RE.match(leaf))


class OutboundSanitizer:
    """Whitelist-first outbound sanitizer: only schema metadata leaves; free text is scrubbed."""

    def __init__(self, secrets: list[str] | tuple[str, ...] = (), documents: list[Any] | tuple[Any, ...] = ()):
        self.secrets: set[str] = set()
        for value in secrets:
            self.add_secret(value)
        for doc in documents:
            self.collect_secrets(doc)

    def add_secret(self, value: Any) -> None:
        if isinstance(value, (str, int, float)) and not isinstance(value, bool):
            raw = str(value).strip()
            if not raw:
                return
            self.secrets.add(raw)
            self.secrets.add(quote(raw, safe=""))
            try:
                self.secrets.add(base64.b64encode(raw.encode("utf-8")).decode("ascii"))
            except Exception:
                pass
            if re.match(r"(?i)^(bearer|basic)\s+", raw):
                parts = raw.split(None, 1)
                if len(parts) == 2 and parts[1].strip():
                    self.secrets.add(parts[1].strip())
            for cookie in raw.split(";"):
                if "=" in cookie:
                    val = cookie.split("=", 1)[1].strip()
                    if val:
                        self.secrets.add(val)

    def collect_secrets(self, value: Any, sensitive: bool = False) -> None:
        if isinstance(value, dict):
            for key, child in value.items():
                key_str = str(key)
                child_sensitive = sensitive or bool(SENSITIVE_KEY_RE.search(key_str)) or key_str.lower() == "auth"
                self.collect_secrets(child, child_sensitive)
        elif isinstance(value, list):
            for child in value[:20]:
                self.collect_secrets(child, sensitive)
        elif sensitive:
            self.add_secret(value)

    def scrub_text(self, value: Any, limit: int = 800) -> str:
        result = str(value or "")
        for secret in sorted(self.secrets, key=len, reverse=True):
            if secret:
                result = result.replace(secret, "[REDACTED]")
        result = _PERSONAL_RE.sub("[REDACTED]", result)
        result = re.sub(
            r"(?i)(password|passwd|token|secret|api[_-]?key|姓名|住址|地址|密码|密钥)\s*[:=：]\s*[^\s,，;；]+",
            r"\1=[REDACTED]",
            result,
        )
        return result[:limit]

    def scrub_identifier(self, value: Any) -> str:
        """Only apply secret values >= IDENTIFIER_SECRET_MIN chars so short values like 'id' never hide 'user_id'."""
        result = str(value or "")
        for secret in sorted(
            (s for s in self.secrets if len(s) >= IDENTIFIER_SECRET_MIN),
            key=len,
            reverse=True,
        ):
            result = result.replace(secret, "[REDACTED]")
        return result

    def allowed_field_name(self, name: str) -> bool:
        if len(name) > 100:
            return False
        if SENSITIVE_KEY_RE.search(name):
            return False
        return self.scrub_identifier(name) == name


def build_safe_response_schema_summary(
    status_code: int | None,
    response_body: Any,
    sanitizer: OutboundSanitizer,
    *,
    max_nodes: int = DEFAULT_MAX_SCHEMA_NODES,
    max_depth: int = DEFAULT_MAX_SCHEMA_DEPTH,
) -> list[dict[str, Any]]:
    """Build a strict whitelist metadata tree (path + type only; zero business values leave)."""
    fields: list[dict[str, Any]] = []
    if isinstance(status_code, int):
        fields.append({"path": "status_code", "type": "number", "value": status_code})

    def visit(node: Any, path: str, depth: int) -> None:
        if len(fields) >= max_nodes or depth > max_depth:
            return
        node_type = json_value_type(node)
        entry: dict[str, Any] = {"path": path, "type": node_type}
        if node_type == "string":
            entry["non_empty"] = bool(str(node).strip())
        elif node_type == "array":
            entry["length"] = len(node)
        elif node_type == "object":
            entry["key_count"] = len(node)
        fields.append(entry)

        if isinstance(node, dict):
            for key, child in node.items():
                key_str = str(key)
                if not sanitizer.allowed_field_name(key_str):
                    continue
                child_path = f"{path}.{key_str}" if path != "$" else f"$.{key_str}"
                visit(child, child_path, depth + 1)
        elif isinstance(node, list):
            for idx, child in enumerate(node[:3]):
                visit(child, f"{path}[{idx}]", depth + 1)

    if response_body is not None:
        visit(response_body, "$", 0)
    return fields
