"""工作流跨节点动态变量总线与表达式求值器服务 (T1.2)

负责在多协议、跨端混合工作流执行过程中传递并动态求值上下文变量:
1. 占位符插值解析: {{node_id.output.path.to.field}} 或 {{env.VAR_NAME}};
2. 点分属性与数组切片安全提取 (a.b.c[0].d);
3. 递归字典/列表/字符串配置参数动态求值注入;
4. 全局租户环境与用例执行上下文隔离。
"""

from __future__ import annotations

import re
from typing import Any, Dict, List, Optional

_PLACEHOLDER_PATTERN = re.compile(r"\{\{([a-zA-Z0-9_\.\[\]]+)\}\}")


def extract_field_by_path(root_data: Any, path: str, default: Any = None) -> Any:
    """按点分路径提取多层嵌套字典与列表值 (如 'node_1.output.order_id' 或 'items[0].name')"""
    if not path:
        return root_data

    # 将 a[0].b 统一转换为 a.0.b
    normalized_path = re.sub(r"\[(\d+)\]", r".\1", path)
    tokens: List[str] = [t.strip() for t in normalized_path.split(".") if t.strip()]

    curr: Any = root_data
    for token in tokens:
        if curr is None:
            return default

        if isinstance(curr, dict):
            if token in curr:
                curr = curr[token]
            else:
                return default
        elif isinstance(curr, list):
            try:
                idx = int(token)
                if 0 <= idx < len(curr):
                    curr = curr[idx]
                else:
                    return default
            except ValueError:
                return default
        else:
            # 尝试通过属性读取
            if hasattr(curr, token):
                curr = getattr(curr, token)
            else:
                return default

    return curr if curr is not None else default


class WorkflowVariableBus:
    """跨节点工作流执行变量总线"""

    def __init__(self, initial_vars: Optional[Dict[str, Any]] = None):
        self._store: Dict[str, Any] = dict(initial_vars or {})

    def set_value(self, key: str, value: Any) -> None:
        self._store[key] = value

    def get_value(self, path: str, default: Any = None) -> Any:
        return extract_field_by_path(self._store, path, default)

    def to_dict(self) -> Dict[str, Any]:
        return dict(self._store)

    def resolve_template_string(self, text: str) -> Any:
        """解析并替换字符串中的 {{placeholder}} 变量

        若字符串恰好全等于 '{{path}}'，直接返回原对象的真实数据类型 (支持数字、字典、列表)；
        若包含普通文本连接，则返回拼接后的字符串。
        """
        match = _PLACEHOLDER_PATTERN.fullmatch(text.strip())
        if match:
            path = match.group(1)
            return self.get_value(path, default=text)

        def _repl(m: re.Match[str]) -> str:
            path = m.group(1)
            val = self.get_value(path, default=m.group(0))
            return str(val)

        return _PLACEHOLDER_PATTERN.sub(_repl, text)

    def resolve_any(self, data: Any) -> Any:
        """递归遍历任意数据结构，解析其中的变量占位符"""
        if isinstance(data, str):
            return self.resolve_template_string(data)
        if isinstance(data, dict):
            return {k: self.resolve_any(v) for k, v in data.items()}
        if isinstance(data, list):
            return [self.resolve_any(item) for item in data]
        return data


def resolve_node_inputs(
    raw_config: Dict[str, Any],
    variable_bus: WorkflowVariableBus,
) -> Dict[str, Any]:
    """为目标节点输入参数注入动态上下文"""
    return variable_bus.resolve_any(raw_config)
