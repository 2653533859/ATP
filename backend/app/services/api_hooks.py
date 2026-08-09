"""受限的 API 前置/后置动作执行器。

这里不执行用户提交的 Python/JavaScript。动作只允许修改当前请求上下文或
对响应做提取/断言，避免测试配置变成任意代码执行入口。
"""

from __future__ import annotations

import re
from defusedxml import ElementTree as ET
from typing import Any

from jsonpath_ng import parse as jp_parse


class ApiHookError(ValueError):
    """API 前置/后置动作配置不合法。"""


_VARIABLE_NAME = re.compile(r"^[A-Za-z_][A-Za-z0-9_]{0,127}$")
_MAX_ACTIONS = 50


def execute_api_hooks(
    actions: list[dict[str, Any]] | None,
    context: dict[str, Any],
    *,
    response_body: Any = None,
    response_headers: dict[str, Any] | None = None,
) -> list[dict[str, Any]]:
    """执行安全动作并返回可用于审计的动作摘要。"""

    if not actions:
        return []
    if not isinstance(actions, list) or len(actions) > _MAX_ACTIONS:
        raise ApiHookError(f"API 钩子动作数量必须在 1 到 {_MAX_ACTIONS} 之间")

    summaries: list[dict[str, Any]] = []
    for index, action in enumerate(actions):
        if not isinstance(action, dict):
            raise ApiHookError(f"第 {index + 1} 个钩子动作不是对象")
        kind = str(action.get("action", "")).strip()
        if kind == "set_variable":
            variable = _require_variable(action.get("variable"), index)
            context[variable] = _render(action.get("value", ""), context)
            summaries.append({"action": kind, "variable": variable})
        elif kind == "delete_variable":
            variable = _require_variable(action.get("variable"), index)
            context.pop(variable, None)
            summaries.append({"action": kind, "variable": variable})
        elif kind == "extract":
            variable = _require_variable(action.get("variable"), index)
            expression = str(action.get("expression", "")).strip()
            if not expression:
                raise ApiHookError(f"第 {index + 1} 个提取动作缺少 expression")
            source = action.get("source", "body")
            actual = _extract(source, expression, action.get("type", "jsonpath"), response_body, response_headers)
            if actual is None:
                raise ApiHookError(f"第 {index + 1} 个提取动作未找到值")
            context[variable] = actual
            summaries.append({"action": kind, "variable": variable, "source": source})
        elif kind == "assert":
            variable = _require_variable(action.get("variable"), index)
            operator = str(action.get("operator", "eq"))
            expected = _render(action.get("expected"), context)
            actual = context.get(variable)
            if not _compare(actual, operator, expected):
                raise ApiHookError(f"第 {index + 1} 个断言动作失败 [{variable}] 期望: {expected}, 实际: {actual}")
            summaries.append({"action": kind, "variable": variable, "operator": operator})
        else:
            raise ApiHookError(f"第 {index + 1} 个钩子动作类型不支持: {kind or '<empty>'}")
    return summaries


def _require_variable(value: Any, index: int) -> str:
    variable = str(value or "").strip()
    if not _VARIABLE_NAME.fullmatch(variable):
        raise ApiHookError(f"第 {index + 1} 个钩子的变量名不合法")
    return variable


def _render(value: Any, context: dict[str, Any]) -> Any:
    if isinstance(value, str):
        for key, item in context.items():
            value = value.replace(f"{{{{{key}}}}}", str(item))
        return value
    if isinstance(value, list):
        return [_render(item, context) for item in value]
    if isinstance(value, dict):
        return {key: _render(item, context) for key, item in value.items()}
    return value


def _extract(source: str, expression: str, expression_type: str, body: Any, headers: dict[str, Any] | None):
    if source == "header":
        return (headers or {}).get(expression)
    if source != "body":
        raise ApiHookError(f"不支持的钩子提取来源: {source}")
    if expression_type == "xpath":
        if not isinstance(body, str):
            return None
        try:
            root = ET.fromstring(body)
            path, _, attribute = expression.rpartition("/@")
            node = root if path in {"", "."} else root.find(f".{path}" if path.startswith("/") else path)
            if node is None:
                return None
            return node.attrib.get(attribute) if attribute else node.text
        except (ET.ParseError, SyntaxError, ValueError):
            return None
    try:
        matches = jp_parse(expression).find(body)
        return matches[0].value if matches else None
    except Exception:
        return None


def _compare(actual: Any, operator: str, expected: Any) -> bool:
    if operator == "eq":
        return str(actual) == str(expected)
    if operator == "contains":
        return str(expected) in str(actual)
    if operator == "exists":
        return actual is not None
    if operator == "not_exists":
        return actual is None
    raise ApiHookError(f"不支持的钩子断言操作符: {operator}")
