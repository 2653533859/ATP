"""代码变更行一阶语法变异算子注入生成引擎 (S3.1).

基于 Python AST 语法树遍历与可执行代码反解析 (ast.unparse)，
在 Git 变更代码行精确注入关系运算反转 (ROR)、逻辑连接替换 (LCR)、算术操作符变异 (AOR)、
返回值置空篡改 (RVO) 与边界值偏移 (BVO) 等经典一阶变异体。
"""

from __future__ import annotations

import ast
import copy
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
import logging
from typing import Any
import uuid

logger = logging.getLogger(__name__)


class MutationOperatorType(str, Enum):
    ROR = "ROR"  # Relational Operator Replacement (关系/比较运算符反转: == <-> !=, < <-> >= 等)
    LCR = "LCR"  # Logical Connector Replacement (逻辑连接符替换: and <-> or)
    AOR = "AOR"  # Arithmetic Operator Replacement (算术运算符替换: + <-> -, * <-> /)
    RVO = "RVO"  # Return Value Overwrite (返回值置空/真假翻转篡改)
    BVO = "BVO"  # Boundary Value Offset (常数边界值 ±1 偏移)


@dataclass
class MutantItem:
    mutant_id: str
    file_path: str
    line_number: int
    operator_type: MutationOperatorType
    original_token: str
    mutated_token: str
    original_line: str
    mutated_line: str
    mutated_code: str
    description: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "mutant_id": self.mutant_id,
            "file_path": self.file_path,
            "line_number": self.line_number,
            "operator_type": self.operator_type.value,
            "original_token": self.original_token,
            "mutated_token": self.mutated_token,
            "original_line": self.original_line,
            "mutated_line": self.mutated_line,
            "mutated_code": self.mutated_code,
            "description": self.description,
        }


@dataclass
class MutationGenerationReport:
    generation_id: str
    file_path: str
    total_mutants_generated: int
    operator_distribution: dict[str, int]
    target_lines_count: int
    mutants: list[MutantItem]
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def to_dict(self) -> dict[str, Any]:
        return {
            "generation_id": self.generation_id,
            "file_path": self.file_path,
            "total_mutants_generated": self.total_mutants_generated,
            "operator_distribution": self.operator_distribution,
            "target_lines_count": self.target_lines_count,
            "mutants": [m.to_dict() for m in self.mutants],
            "created_at": self.created_at.isoformat(),
        }


# 内存变异体与报告仓库
_MUTANT_STORE: dict[str, MutantItem] = {}
_GENERATION_REPORTS: dict[str, MutationGenerationReport] = {}

# ROR 运算符映射表
_ROR_MAP: dict[type[ast.cmpop], tuple[type[ast.cmpop], str, str]] = {
    ast.Eq: (ast.NotEq, "==", "!="),
    ast.NotEq: (ast.Eq, "!=", "=="),
    ast.Lt: (ast.GtE, "<", ">="),
    ast.GtE: (ast.Lt, ">=", "<"),
    ast.Gt: (ast.LtE, ">", "<="),
    ast.LtE: (ast.Gt, "<=", ">"),
    ast.In: (ast.NotIn, "in", "not in"),
    ast.NotIn: (ast.In, "not in", "in"),
    ast.Is: (ast.IsNot, "is", "is not"),
    ast.IsNot: (ast.Is, "is not", "is"),
}

# LCR 逻辑运算符映射表
_LCR_MAP: dict[type[ast.boolop], tuple[type[ast.boolop], str, str]] = {
    ast.And: (ast.Or, "and", "or"),
    ast.Or: (ast.And, "or", "and"),
}

# AOR 算术运算符映射表
_AOR_MAP: dict[type[ast.operator], tuple[type[ast.operator], str, str]] = {
    ast.Add: (ast.Sub, "+", "-"),
    ast.Sub: (ast.Add, "-", "+"),
    ast.Mult: (ast.FloorDiv, "*", "//"),
}


def _get_line_text(code: str, lineno: int) -> str:
    """按行号获取原始代码单行文本。"""
    lines = code.splitlines()
    if 1 <= lineno <= len(lines):
        return lines[lineno - 1].strip()
    return ""


def generate_code_mutants(
    source_code: str,
    file_path: str = "main.py",
    target_lines: list[int] | None = None,
    max_mutants: int = 25,
) -> MutationGenerationReport:
    """对指定 Python 源码在目标行精准生成一阶语法变异体集合。"""
    generation_id = f"gen_{uuid.uuid4().hex[:12]}"
    mutants: list[MutantItem] = []
    target_set = set(target_lines) if target_lines is not None else None

    try:
        base_tree = ast.parse(source_code, filename=file_path)
    except SyntaxError as exc:
        logger.warning("Failed to parse code for mutations %s: %s", file_path, exc)
        return MutationGenerationReport(
            generation_id=generation_id,
            file_path=file_path,
            total_mutants_generated=0,
            operator_distribution={},
            target_lines_count=len(target_set) if target_set else 0,
            mutants=[],
        )

    # 递归遍历寻找所有可变异的 AST 节点
    for node in ast.walk(base_tree):
        if len(mutants) >= max_mutants:
            break

        lineno = getattr(node, "lineno", None)
        if lineno is None:
            continue

        # 若限制了目标变更行，且当前节点不在目标行则跳过
        if target_set is not None and lineno not in target_set:
            continue

        orig_line_text = _get_line_text(source_code, lineno)

        # 1. 检查 ROR (关系运算反转)
        if isinstance(node, ast.Compare):
            for idx, op in enumerate(node.ops):
                cmp_op_cls = type(op)
                if cmp_op_cls in _ROR_MAP and len(mutants) < max_mutants:
                    target_cmp_op_cls, cmp_orig_str, cmp_mut_str = _ROR_MAP[cmp_op_cls]
                    mutated_tree = copy.deepcopy(base_tree)

                    # 找到对应节点并替换算子
                    for m_node in ast.walk(mutated_tree):
                        if (
                            getattr(m_node, "lineno", None) == lineno
                            and isinstance(m_node, ast.Compare)
                            and len(m_node.ops) > idx
                            and isinstance(m_node.ops[idx], cmp_op_cls)
                        ):
                            m_node.ops[idx] = target_cmp_op_cls()
                            break

                    mutated_code = ast.unparse(mutated_tree)
                    mut_line_text = _get_line_text(mutated_code, lineno)
                    mutant_id = f"mut_ror_{uuid.uuid4().hex[:10]}"
                    m_item = MutantItem(
                        mutant_id=mutant_id,
                        file_path=file_path,
                        line_number=lineno,
                        operator_type=MutationOperatorType.ROR,
                        original_token=cmp_orig_str,
                        mutated_token=cmp_mut_str,
                        original_line=orig_line_text,
                        mutated_line=mut_line_text,
                        mutated_code=mutated_code,
                        description=f"关系条件反转: 将 '{cmp_orig_str}' 变异替换为 '{cmp_mut_str}'",
                    )
                    mutants.append(m_item)
                    _MUTANT_STORE[mutant_id] = m_item

        # 2. 检查 LCR (逻辑连接符替换 and <-> or)
        elif isinstance(node, ast.BoolOp):
            bool_op_cls = type(node.op)
            if bool_op_cls in _LCR_MAP and len(mutants) < max_mutants:
                target_bool_op_cls, bool_orig_str, bool_mut_str = _LCR_MAP[bool_op_cls]
                mutated_tree = copy.deepcopy(base_tree)

                for m_node in ast.walk(mutated_tree):
                    if (
                        getattr(m_node, "lineno", None) == lineno
                        and isinstance(m_node, ast.BoolOp)
                        and isinstance(m_node.op, bool_op_cls)
                    ):
                        m_node.op = target_bool_op_cls()
                        break

                mutated_code = ast.unparse(mutated_tree)
                mut_line_text = _get_line_text(mutated_code, lineno)
                mutant_id = f"mut_lcr_{uuid.uuid4().hex[:10]}"
                m_item = MutantItem(
                    mutant_id=mutant_id,
                    file_path=file_path,
                    line_number=lineno,
                    operator_type=MutationOperatorType.LCR,
                    original_token=bool_orig_str,
                    mutated_token=bool_mut_str,
                    original_line=orig_line_text,
                    mutated_line=mut_line_text,
                    mutated_code=mutated_code,
                    description=f"逻辑连接符替换: 将 '{bool_orig_str}' 变异替换为 '{bool_mut_str}'",
                )
                mutants.append(m_item)
                _MUTANT_STORE[mutant_id] = m_item

        # 3. 检查 AOR (算术运算符替换 + <-> -, * <-> //)
        elif isinstance(node, ast.BinOp):
            bin_op_cls = type(node.op)
            if bin_op_cls in _AOR_MAP and len(mutants) < max_mutants:
                target_bin_op_cls, bin_orig_str, bin_mut_str = _AOR_MAP[bin_op_cls]
                mutated_tree = copy.deepcopy(base_tree)

                for m_node in ast.walk(mutated_tree):
                    if (
                        getattr(m_node, "lineno", None) == lineno
                        and isinstance(m_node, ast.BinOp)
                        and isinstance(m_node.op, bin_op_cls)
                    ):
                        m_node.op = target_bin_op_cls()
                        break

                mutated_code = ast.unparse(mutated_tree)
                mut_line_text = _get_line_text(mutated_code, lineno)
                mutant_id = f"mut_aor_{uuid.uuid4().hex[:10]}"
                m_item = MutantItem(
                    mutant_id=mutant_id,
                    file_path=file_path,
                    line_number=lineno,
                    operator_type=MutationOperatorType.AOR,
                    original_token=bin_orig_str,
                    mutated_token=bin_mut_str,
                    original_line=orig_line_text,
                    mutated_line=mut_line_text,
                    mutated_code=mutated_code,
                    description=f"算术运算符变异: 将 '{bin_orig_str}' 变异替换为 '{bin_mut_str}'",
                )
                mutants.append(m_item)
                _MUTANT_STORE[mutant_id] = m_item

        # 4. 检查 RVO (返回值篡改)
        elif isinstance(node, ast.Return) and len(mutants) < max_mutants:
            mutated_tree = copy.deepcopy(base_tree)
            orig_val_repr = ast.unparse(node.value) if node.value else "None"
            mut_val_repr = "None"
            for m_node in ast.walk(mutated_tree):
                if getattr(m_node, "lineno", None) == lineno and isinstance(m_node, ast.Return):
                    # 若原本返回 True，变更为 False；反之亦然；若其他表达式则置为 None
                    if isinstance(node.value, ast.Constant) and isinstance(node.value.value, bool):
                        m_node.value = ast.Constant(value=not node.value.value)
                        mut_val_repr = str(not node.value.value)
                    else:
                        m_node.value = ast.Constant(value=None)
                        mut_val_repr = "None"
                    break

            mutated_code = ast.unparse(mutated_tree)
            mut_line_text = _get_line_text(mutated_code, lineno)
            mutant_id = f"mut_rvo_{uuid.uuid4().hex[:10]}"
            m_item = MutantItem(
                mutant_id=mutant_id,
                file_path=file_path,
                line_number=lineno,
                operator_type=MutationOperatorType.RVO,
                original_token=orig_val_repr,
                mutated_token=mut_val_repr,
                original_line=orig_line_text,
                mutated_line=mut_line_text,
                mutated_code=mutated_code,
                description=f"返回值篡改: 将返回值 '{orig_val_repr}' 变异为 '{mut_val_repr}'",
            )
            mutants.append(m_item)
            _MUTANT_STORE[mutant_id] = m_item

        # 5. 检查 BVO (常数边界值 ±1 偏移)
        elif isinstance(node, ast.Constant) and isinstance(node.value, int) and not isinstance(node.value, bool):
            if len(mutants) < max_mutants:
                orig_int = node.value
                mut_int = orig_int + 1
                mutated_tree = copy.deepcopy(base_tree)

                for m_node in ast.walk(mutated_tree):
                    if (
                        getattr(m_node, "lineno", None) == lineno
                        and isinstance(m_node, ast.Constant)
                        and m_node.value == orig_int
                        and not isinstance(m_node.value, bool)
                    ):
                        m_node.value = mut_int
                        break

                mutated_code = ast.unparse(mutated_tree)
                mut_line_text = _get_line_text(mutated_code, lineno)
                mutant_id = f"mut_bvo_{uuid.uuid4().hex[:10]}"
                m_item = MutantItem(
                    mutant_id=mutant_id,
                    file_path=file_path,
                    line_number=lineno,
                    operator_type=MutationOperatorType.BVO,
                    original_token=str(orig_int),
                    mutated_token=str(mut_int),
                    original_line=orig_line_text,
                    mutated_line=mut_line_text,
                    mutated_code=mutated_code,
                    description=f"边界常数偏移: 将边界数值 {orig_int} 变异偏移为 {mut_int}",
                )
                mutants.append(m_item)
                _MUTANT_STORE[mutant_id] = m_item

    # 统计算子分布
    dist: dict[str, int] = {}
    for m in mutants:
        dist[m.operator_type.value] = dist.get(m.operator_type.value, 0) + 1

    report = MutationGenerationReport(
        generation_id=generation_id,
        file_path=file_path,
        total_mutants_generated=len(mutants),
        operator_distribution=dist,
        target_lines_count=len(target_set) if target_set else len(source_code.splitlines()),
        mutants=mutants,
    )

    _GENERATION_REPORTS[generation_id] = report
    logger.info(
        "Generated %d mutants for %s across operators: %s",
        len(mutants),
        file_path,
        dist,
    )
    return report


def get_mutant_by_id(mutant_id: str) -> MutantItem | None:
    """按 ID 查询单个变异体。"""
    return _MUTANT_STORE.get(mutant_id)


def get_mutation_report(generation_id: str) -> MutationGenerationReport | None:
    """按 ID 获取变异体生成报告。"""
    return _GENERATION_REPORTS.get(generation_id)


def list_mutation_reports() -> list[MutationGenerationReport]:
    """查询历史变异体生成报告列表。"""
    return list(_GENERATION_REPORTS.values())


def reset_mutation_registry() -> None:
    """单元测试清理状态使用。"""
    _MUTANT_STORE.clear()
    _GENERATION_REPORTS.clear()
