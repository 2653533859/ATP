"""Run-scoped dataset preparation actions.

Preparation is intentionally a small DSL. It can seed a test service through
bounded HTTP requests and pass extracted values to every dataset iteration,
but it never executes user supplied Python or JavaScript and never mutates the
persisted dataset.
"""

from __future__ import annotations

import asyncio
from collections.abc import Mapping
from typing import Any

import httpx
from jsonpath_ng import parse as jp_parse

from app.core.url_security import validate_public_http_url
from app.services.api_hooks import ApiHookError, execute_api_hooks

MAX_PREPARATION_ACTIONS = 20
MAX_REQUEST_TIMEOUT_SECONDS = 60.0
MAX_RESPONSE_BYTES = 1024 * 1024
SUPPORTED_REQUEST_METHODS = {"DELETE", "GET", "HEAD", "OPTIONS", "PATCH", "POST", "PUT"}
SUPPORTED_BODY_TYPES = {"json", "raw", "none"}


class DatasetPreparationError(ValueError):
    """Raised when a preparation action is invalid or fails."""


async def execute_dataset_preparation(
    actions: list[dict[str, Any]] | None,
    context: dict[str, Any],
) -> list[dict[str, Any]]:
    """Execute preparation actions and return a secret-free audit summary."""

    if actions is None or actions == []:
        return []
    if not isinstance(actions, list) or len(actions) > MAX_PREPARATION_ACTIONS:
        raise DatasetPreparationError(f"数据准备动作数量必须在 1 到 {MAX_PREPARATION_ACTIONS} 之间")

    summaries: list[dict[str, Any]] = []
    async with httpx.AsyncClient(follow_redirects=False) as client:
        for index, action in enumerate(actions):
            if not isinstance(action, dict):
                raise _action_error(index, "动作必须是对象")
            kind = str(action.get("action", "")).strip()
            try:
                if kind == "request":
                    summaries.append(await _execute_request(client, index, action, context))
                elif kind in {"set_variable", "delete_variable", "extract", "assert"}:
                    # Reuse the same allowlist and validation as API hooks. For
                    # extract, a response must come from a request action; the
                    # direct form is rejected by execute_api_hooks.
                    hook_summary = execute_api_hooks([action], context)
                    summaries.extend({"action": item["action"], **_safe_item(item)} for item in hook_summary)
                else:
                    raise _action_error(index, f"不支持的动作类型: {kind or '<empty>'}")
            except DatasetPreparationError:
                raise
            except (ApiHookError, httpx.HTTPError, ValueError, TypeError) as exc:
                raise _action_error(index, _safe_error_message(exc)) from exc
    return summaries


async def _execute_request(
    client: httpx.AsyncClient,
    index: int,
    action: Mapping[str, Any],
    context: dict[str, Any],
) -> dict[str, Any]:
    method = str(action.get("method", "POST")).strip().upper()
    if method not in SUPPORTED_REQUEST_METHODS:
        raise _action_error(index, f"不支持的 HTTP 方法: {method or '<empty>'}")

    url = _render(action.get("url", ""), context)
    if not isinstance(url, str) or not url.strip():
        raise _action_error(index, "request 动作缺少 url")
    try:
        # Resolve every address before the request so a user-configured seed
        # URL cannot target localhost, link-local or private infrastructure.
        url = await asyncio.to_thread(validate_public_http_url, url)
    except ValueError as exc:
        raise _action_error(index, f"URL 不合法: {exc}") from exc

    try:
        timeout = float(action.get("timeout", 30))
    except (TypeError, ValueError) as exc:
        raise _action_error(index, "timeout 必须是数字") from exc
    if not 0.1 <= timeout <= MAX_REQUEST_TIMEOUT_SECONDS:
        raise _action_error(index, f"timeout 必须在 0.1 到 {MAX_REQUEST_TIMEOUT_SECONDS:g} 秒之间")

    body_type = str(action.get("body_type", "json" if isinstance(action.get("body"), (dict, list)) else "raw"))
    if body_type not in SUPPORTED_BODY_TYPES:
        raise _action_error(index, f"不支持的 body_type: {body_type}")

    kwargs: dict[str, Any] = {
        "headers": _render_mapping(action.get("headers", {}), context),
        "params": _render_mapping(action.get("params", {}), context),
    }
    body = _render(action.get("body"), context)
    if body is not None and body_type != "none":
        if body_type == "json":
            kwargs["json"] = body
        else:
            kwargs["content"] = str(body)

    response = await client.request(method, url, timeout=timeout, **kwargs)
    if len(response.content) > MAX_RESPONSE_BYTES:
        raise _action_error(index, f"响应体超过 {MAX_RESPONSE_BYTES // 1024}KB 限制")
    response_body = _parse_response(response)

    _assert_preparation_results(index, action.get("assertions"), response, response_body, context)
    post_actions = action.get("post_actions")
    if post_actions is not None:
        if not isinstance(post_actions, list):
            raise _action_error(index, "post_actions 必须是 JSON 数组")
        try:
            execute_api_hooks(
                post_actions,
                context,
                response_body=response_body,
                response_headers=dict(response.headers),
            )
        except ApiHookError as exc:
            raise _action_error(index, str(exc)) from exc

    return {
        "action": "request",
        "name": str(action.get("name", "")).strip()[:128] or f"request_{index + 1}",
        "method": method,
        "status_code": response.status_code,
        "post_action_count": len(post_actions or []),
    }


def _assert_preparation_results(
    index: int,
    assertions: Any,
    response: httpx.Response,
    response_body: Any,
    context: dict[str, Any],
) -> None:
    if assertions is None:
        return
    if not isinstance(assertions, list) or len(assertions) > 20:
        raise _action_error(index, "assertions 必须是不超过 20 项的数组")
    for assertion_index, assertion in enumerate(assertions):
        if not isinstance(assertion, dict):
            raise _action_error(index, f"第 {assertion_index + 1} 个断言必须是对象")
        source = str(assertion.get("source", "status")).strip().lower()
        operator = str(assertion.get("operator", "eq")).strip().lower()
        expected = _render(assertion.get("expected"), context)
        if source == "status":
            actual: Any = response.status_code
        elif source == "header":
            header = str(assertion.get("field", "")).strip()
            if not header:
                raise _action_error(index, "header 断言缺少 field")
            actual = response.headers.get(header)
        elif source == "body":
            expression = str(assertion.get("expression", "")).strip()
            if not expression:
                raise _action_error(index, "body 断言缺少 expression")
            try:
                matches = jp_parse(expression).find(response_body)
            except Exception as exc:
                raise _action_error(index, f"第 {assertion_index + 1} 个 body 表达式无效") from exc
            actual = matches[0].value if matches else None
            if not _compare(actual, operator, expected):
                raise _action_error(index, f"第 {assertion_index + 1} 个 body 断言失败")
            continue
        else:
            raise _action_error(index, f"不支持的断言来源: {source}")
        if not _compare(actual, operator, expected):
            raise _action_error(index, f"第 {assertion_index + 1} 个断言失败")


def _compare(actual: Any, operator: str, expected: Any) -> bool:
    if operator == "eq":
        return str(actual) == str(expected)
    if operator == "contains":
        return str(expected) in str(actual)
    if operator == "exists":
        return actual is not None
    if operator == "not_exists":
        return actual is None
    raise DatasetPreparationError(f"不支持的断言操作符: {operator}")


def _parse_response(response: httpx.Response) -> Any:
    content_type = response.headers.get("content-type", "").lower()
    if "json" in content_type:
        try:
            return response.json()
        except ValueError:
            return response.text
    try:
        return response.json()
    except ValueError:
        return response.text


def _render(value: Any, context: Mapping[str, Any]) -> Any:
    if isinstance(value, str):
        for key, item in context.items():
            value = value.replace(f"{{{{{key}}}}}", str(item))
        return value
    if isinstance(value, list):
        return [_render(item, context) for item in value]
    if isinstance(value, dict):
        return {key: _render(item, context) for key, item in value.items()}
    return value


def _render_mapping(value: Any, context: Mapping[str, Any]) -> dict[str, Any]:
    if value is None:
        return {}
    if not isinstance(value, dict):
        raise DatasetPreparationError("headers 和 params 必须是对象")
    return {str(key): _render(item, context) for key, item in value.items()}


def _action_error(index: int, message: str) -> DatasetPreparationError:
    return DatasetPreparationError(f"第 {index + 1} 个数据准备动作失败: {message}")


def _safe_item(item: Mapping[str, Any]) -> dict[str, Any]:
    return {key: value for key, value in item.items() if key in {"action", "variable", "source", "operator"}}


def _safe_error_message(error: Exception) -> str:
    message = str(error).strip()
    return message[:300] or error.__class__.__name__


__all__ = [
    "DatasetPreparationError",
    "MAX_PREPARATION_ACTIONS",
    "execute_dataset_preparation",
]
