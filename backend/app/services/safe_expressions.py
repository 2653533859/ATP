"""Small AST-based expression evaluator for API assertions."""

from __future__ import annotations

import ast
import operator
from collections.abc import Mapping
from typing import Any


class SafeExpressionError(ValueError):
    """Raised when a restricted expression is invalid or unsafe."""


_COMPARES = {
    ast.Eq: operator.eq,
    ast.NotEq: operator.ne,
    ast.Lt: operator.lt,
    ast.LtE: operator.le,
    ast.Gt: operator.gt,
    ast.GtE: operator.ge,
    ast.In: lambda left, right: left in right,
    ast.NotIn: lambda left, right: left not in right,
    ast.Is: operator.is_,
    ast.IsNot: operator.is_not,
}


def evaluate_safe_expression(expression: str, context: Mapping[str, Any]) -> Any:
    if not isinstance(expression, str) or not expression.strip() or len(expression) > 512:
        raise SafeExpressionError("表达式不能为空且长度不能超过 512 个字符")
    try:
        tree = ast.parse(expression, mode="eval")
    except SyntaxError as exc:
        raise SafeExpressionError("表达式语法不合法") from exc
    if sum(1 for _ in ast.walk(tree)) > 100:
        raise SafeExpressionError("表达式复杂度超过限制")
    return _evaluate(tree.body, context)


def _evaluate(node: ast.AST, context: Mapping[str, Any]) -> Any:
    if isinstance(node, ast.Constant) and isinstance(node.value, (str, int, float, bool, type(None))):
        return node.value
    if isinstance(node, ast.Name):
        if node.id not in context:
            raise SafeExpressionError(f"未定义变量: {node.id}")
        return context[node.id]
    if isinstance(node, ast.Attribute):
        if node.attr.startswith("_"):
            raise SafeExpressionError("禁止访问私有属性")
        return _lookup(_evaluate(node.value, context), node.attr)
    if isinstance(node, ast.Subscript):
        return _lookup(_evaluate(node.value, context), _evaluate(node.slice, context))
    if isinstance(node, (ast.List, ast.Tuple, ast.Set)):
        values = [_evaluate(item, context) for item in node.elts]
        if isinstance(node, ast.List):
            return values
        if isinstance(node, ast.Tuple):
            return tuple(values)
        return set(values)
    if isinstance(node, ast.BoolOp):
        if isinstance(node.op, ast.And):
            result = True
            for value in node.values:
                result = _evaluate(value, context)
                if not result:
                    return result
            return result
        if isinstance(node.op, ast.Or):
            result = False
            for value in node.values:
                result = _evaluate(value, context)
                if result:
                    return result
            return result
    if isinstance(node, ast.UnaryOp) and isinstance(node.op, ast.Not):
        return not _evaluate(node.operand, context)
    if isinstance(node, ast.Compare):
        left = _evaluate(node.left, context)
        for compare_node, comparator in zip(node.ops, node.comparators, strict=True):
            right = _evaluate(comparator, context)
            compare_fn = next((fn for kind, fn in _COMPARES.items() if isinstance(compare_node, kind)), None)
            if compare_fn is None:
                raise SafeExpressionError("不支持的比较操作")
            try:
                if not compare_fn(left, right):
                    return False
            except (TypeError, ValueError):
                return False
            left = right
        return True
    raise SafeExpressionError("表达式包含不允许的操作")


def _lookup(value: Any, key: Any) -> Any:
    if isinstance(value, Mapping):
        return value.get(key)
    if isinstance(value, (list, tuple)) and isinstance(key, int) and 0 <= key < len(value):
        return value[key]
    if isinstance(key, str) and not key.startswith("_") and hasattr(value, key):
        return getattr(value, key)
    raise SafeExpressionError("表达式只能访问字典字段或公开属性")
