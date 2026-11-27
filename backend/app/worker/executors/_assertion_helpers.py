"""HTTP/GraphQL/WebSocket/gRPC/多协议执行器共享的认证与断言辅助函数。"""

from __future__ import annotations

import base64
from collections.abc import Callable
from typing import Any


def build_basic_auth_header(auth_cfg: dict[str, Any], render_fn: Callable[[Any], str]) -> str:
    """Safely render username/password (treating None as '') and encode Basic token."""
    raw_user = auth_cfg.get("username")
    raw_pass = auth_cfg.get("password")
    username = render_fn("" if raw_user is None else str(raw_user))
    password = render_fn("" if raw_pass is None else str(raw_pass))
    cred = base64.b64encode(f"{username}:{password}".encode("utf-8")).decode("ascii")
    return f"Basic {cred}"


def collect_auth_redact_fields(auth_cfg: dict[str, Any], render_fn: Callable[[Any], str]) -> list[str]:
    """Return header names populated by auth config so step evidence auto-redacts secrets."""
    auth_type = str(auth_cfg.get("type") or "").strip().lower()
    if auth_type in {"bearer", "basic", "oauth2_client_credentials"}:
        return ["authorization"]
    if auth_type == "apikey":
        header_name = render_fn(str(auth_cfg.get("header") or "X-API-Key")).strip()
        if header_name:
            return [header_name.lower()]
    return []


def render_recursive(value: Any, render_fn: Callable[[str], Any]) -> Any:
    """Recursively render template strings inside nested dicts/lists."""
    if isinstance(value, str):
        return render_fn(value)
    if isinstance(value, dict):
        return {k: render_recursive(v, render_fn) for k, v in value.items()}
    if isinstance(value, list):
        return [render_recursive(item, render_fn) for item in value]
    return value


def compare_assertion_operator(
    operator: str | None,
    actual: Any,
    expected: Any,
    *,
    target: str = "",
) -> tuple[bool, str]:
    """Evaluate common assertion operators safely across protocol executors."""
    op = str(operator or "eq").strip().lower()
    if op == "eq":
        ok = str(actual) == str(expected)
    elif op in {"ne", "neq"}:
        ok = str(actual) != str(expected)
        if not ok:
            return False, f"断言失败 [{target}] 期望不等于 '{expected}', 实际: '{actual}'"
        return True, ""
    elif op == "contains":
        if actual is None:
            ok = False
        else:
            needle = "" if expected is None else str(expected)
            ok = needle in str(actual)
    elif op in {"gt", "lt"}:
        if actual is None or expected is None:
            return False, f"断言失败 [{target}] 无法比较空值: expected={expected}, actual={actual}"
        try:
            a_num = float(actual)
            e_num = float(expected)
        except (TypeError, ValueError):
            return False, f"断言失败 [{target}] 非数值无法比较: expected={expected}, actual={actual}"
        ok = a_num > e_num if op == "gt" else a_num < e_num
    elif op == "exists":
        ok = actual is not None
        if not ok:
            return False, f"断言失败 [{target}] 字段不存在或为 None"
        return True, ""
    elif op == "not_empty":
        if actual is None:
            ok = False
        elif isinstance(actual, str):
            ok = bool(actual.strip())
        elif isinstance(actual, (list, dict)):
            ok = len(actual) > 0
        else:
            ok = True
        if not ok:
            return False, f"断言失败 [{target}] 期望非空，实际: {actual!r}"
        return True, ""
    elif op == "not_exists":
        ok = actual is None
    else:
        return False, f"未知断言操作符: {operator}"

    if not ok:
        return False, f"断言失败 [{target}] 期望: {expected}, 实际: {actual}"
    return True, ""
