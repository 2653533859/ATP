"""语义断言智能演进与语法重写器服务 (T2.2)

基于 ResponseSchemaDriftReport 的变迁定义，自动将旧断言语法重写为适应新结构的现代断言:
1. Python AST 语法树遍历与动态变迁节点重写 (AssertionASTDriftTransformer);
2. 字典取值 Subscript 与 .get() 表达式的层级自动展开与键名对齐;
3. 比较操作数类型自适应演进 (Type Coercion Evolution);
4. 标准 Unified Code Diff 与演进置信变更流水生成 (AssertionEvolutionResult)。
"""

from __future__ import annotations

import ast
import difflib
import enum
import uuid
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Tuple

from app.services.response_schema_drift_detector import (
    DriftMutationType,
    ResponseSchemaDriftReport,
    SchemaDriftItem,
)


class EvolutionStatus(str, enum.Enum):
    EVOLVED = "EVOLVED"  # 成功演进并产生代码变更
    UNCHANGED = "UNCHANGED"  # 无需演进或无匹配漂移
    SYNTAX_ERROR = "SYNTAX_ERROR"  # 原始代码语法错误无法解析


@dataclass
class AssertionEvolutionResult:
    evolution_id: str
    original_code: str
    evolved_code: str
    unified_diff: str
    applied_drift_ids: List[str]
    status: EvolutionStatus
    evolution_notes: List[str]
    evolved_at: str = field(default_factory=lambda: datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S"))

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        d["status"] = self.status.value
        return d


def _parse_jsonpath_to_keys(jsonpath: str) -> List[str]:
    """将 JSONPath 转换为字段键名列表 ($.data.user_id -> ['data', 'user_id'])"""
    cleaned = jsonpath.lstrip("$").lstrip(".")
    tokens = []
    for part in cleaned.split("."):
        if not part:
            continue
        # 处理 list 索引如 roles[0]
        if "[" in part and "]" in part:
            p_name = part.split("[")[0]
            if p_name:
                tokens.append(p_name)
        else:
            tokens.append(part)
    return tokens


class AssertionASTDriftTransformer(ast.NodeTransformer):
    """基于 AST 深度遍历重写 Python 断言中的字段访问与类型比较"""

    def __init__(self, drift_items: List[SchemaDriftItem]):
        super().__init__()
        self.drift_items = drift_items
        self.applied_drift_ids: List[str] = []
        self.notes: List[str] = []

        # 映射：旧单键名 -> (新字段层级列表, SchemaDriftItem)
        self.key_map: Dict[str, Tuple[List[str], SchemaDriftItem]] = {}
        for item in drift_items:
            old_keys = _parse_jsonpath_to_keys(item.old_path)
            new_keys = _parse_jsonpath_to_keys(item.new_path)
            if old_keys:
                # 以旧路径的最末尾叶子键作为触发词
                leaf = old_keys[-1]
                self.key_map[leaf] = (new_keys, item)

    def visit_Subscript(self, node: ast.Subscript) -> ast.AST:
        """拦截字典取值表达式: res['user_id'] ➔ res['data']['userId']"""
        self.generic_visit(node)

        # 检查 slice 是否为 Constant 常量字符串
        if isinstance(node.slice, ast.Constant) and isinstance(node.slice.value, str):
            key = node.slice.value
            if key in self.key_map:
                new_keys, drift = self.key_map[key]
                if drift.drift_id not in self.applied_drift_ids:
                    self.applied_drift_ids.append(drift.drift_id)
                self.notes.append(f"字段访问演进 [{drift.mutation_type.value}]: '{key}' ➔ '{'.'.join(new_keys)}'")

                # 将 node.value (如 res) 构建为连续嵌套的 Subscript
                curr_node: ast.expr = node.value
                for k in new_keys:
                    curr_node = ast.Subscript(
                        value=curr_node,
                        slice=ast.Constant(value=k),
                        ctx=ast.Load(),
                    )
                return curr_node

        return node

    def visit_Call(self, node: ast.Call) -> ast.AST:
        """拦截 .get('user_id') 调用: res.get('user_id') ➔ res.get('data', {}).get('userId')"""
        self.generic_visit(node)

        if isinstance(node.func, ast.Attribute) and node.func.attr == "get":
            if node.args and isinstance(node.args[0], ast.Constant) and isinstance(node.args[0].value, str):
                key = node.args[0].value
                if key in self.key_map:
                    new_keys, drift = self.key_map[key]
                    if drift.drift_id not in self.applied_drift_ids:
                        self.applied_drift_ids.append(drift.drift_id)
                    self.notes.append(
                        f"方法调用演进 [{drift.mutation_type.value}]: .get('{key}') ➔ 链式取值 '{'.'.join(new_keys)}'"
                    )

                    curr_node: ast.expr = node.func.value
                    for idx, k in enumerate(new_keys):
                        is_last = idx == len(new_keys) - 1
                        default_arg = node.args[1] if (is_last and len(node.args) > 1) else ast.Dict(keys=[], values=[])
                        curr_node = ast.Call(
                            func=ast.Attribute(value=curr_node, attr="get", ctx=ast.Load()),
                            args=[ast.Constant(value=k)] + ([default_arg] if not is_last or len(node.args) > 1 else []),
                            keywords=[],
                        )
                    return curr_node

        return node

    def visit_Compare(self, node: ast.Compare) -> ast.AST:
        """拦截类型演进的比对常量: 如 assert res['val'] == '0.15' 演进为 0.15"""
        self.generic_visit(node)

        # 检查比较右侧是否需要根据 TYPE_MUTATED 进行类型自适应演进
        for item in self.drift_items:
            if item.mutation_type == DriftMutationType.TYPE_MUTATED:
                # 如果左侧访问了该字段
                for comparator in node.comparators:
                    if isinstance(comparator, ast.Constant):
                        # 若原断言中是字符串 '0.15'，新采样值为浮点数 0.15
                        if isinstance(comparator.value, str) and isinstance(item.new_value_sample, (int, float)):
                            try:
                                coerced_val = type(item.new_value_sample)(comparator.value)
                                comparator.value = coerced_val
                                if item.drift_id not in self.applied_drift_ids:
                                    self.applied_drift_ids.append(item.drift_id)
                                self.notes.append(
                                    f"类型自适应演进: 常量比较值自动由 str '{comparator.value}' 转换为 {type(item.new_value_sample).__name__}"
                                )
                            except (ValueError, TypeError):
                                pass

        return node


def synthesize_assertion_evolution(
    original_code: str,
    drift_source: ResponseSchemaDriftReport | List[SchemaDriftItem],
) -> AssertionEvolutionResult:
    """自动将包含旧路径或失效字段的断言代码演进为适配新 Schema 的现代代码"""
    evolution_id = f"evo_{uuid.uuid4().hex[:10]}"

    try:
        tree = ast.parse(original_code)
    except SyntaxError as e:
        return AssertionEvolutionResult(
            evolution_id=evolution_id,
            original_code=original_code,
            evolved_code=original_code,
            unified_diff="",
            applied_drift_ids=[],
            status=EvolutionStatus.SYNTAX_ERROR,
            evolution_notes=[f"原始断言代码解析失败: {str(e)}"],
        )

    drift_items = drift_source.drifts if isinstance(drift_source, ResponseSchemaDriftReport) else drift_source
    if not drift_items:
        return AssertionEvolutionResult(
            evolution_id=evolution_id,
            original_code=original_code,
            evolved_code=original_code,
            unified_diff="",
            applied_drift_ids=[],
            status=EvolutionStatus.UNCHANGED,
            evolution_notes=["无有效的结构漂移项，断言代码保持原状"],
        )

    transformer = AssertionASTDriftTransformer(drift_items)
    evolved_tree = transformer.visit(tree)
    ast.fix_missing_locations(evolved_tree)

    evolved_code = ast.unparse(evolved_tree)

    # 规范化原始代码与新代码换行
    orig_stripped = original_code.strip()
    evolved_stripped = evolved_code.strip()

    if orig_stripped == evolved_stripped or not transformer.applied_drift_ids:
        return AssertionEvolutionResult(
            evolution_id=evolution_id,
            original_code=original_code,
            evolved_code=original_code,
            unified_diff="",
            applied_drift_ids=[],
            status=EvolutionStatus.UNCHANGED,
            evolution_notes=["断言代码中未引用发生漂移的字段，无需演进"],
        )

    # 生成标准 Unified Diff
    diff_lines = list(
        difflib.unified_diff(
            orig_stripped.splitlines(keepends=True),
            evolved_stripped.splitlines(keepends=True),
            fromfile="original_assertion.py",
            tofile="evolved_assertion.py",
            lineterm="",
        )
    )
    unified_diff = "\n".join(diff_lines)

    return AssertionEvolutionResult(
        evolution_id=evolution_id,
        original_code=orig_stripped,
        evolved_code=evolved_stripped,
        unified_diff=unified_diff,
        applied_drift_ids=transformer.applied_drift_ids,
        status=EvolutionStatus.EVOLVED,
        evolution_notes=transformer.notes,
    )
