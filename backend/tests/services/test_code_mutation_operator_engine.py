"""Unit tests for Code Mutation Operator Engine Service (S3.1)."""

from __future__ import annotations

import pytest

from app.services.code_mutation_operator_engine import (
    MutationOperatorType,
    generate_code_mutants,
    get_mutant_by_id,
    get_mutation_report,
    list_mutation_reports,
    reset_mutation_registry,
)


@pytest.fixture(autouse=True)
def clean_mutations():
    reset_mutation_registry()
    yield
    reset_mutation_registry()


SAMPLE_CODE = """def calculate_discount(price: float, is_vip: bool) -> float:
    if price > 1000 and is_vip:
        discount = price * 0.2
        return discount
    return 0.0
"""


def test_generate_mutants_operators_coverage():
    report = generate_code_mutants(
        source_code=SAMPLE_CODE,
        file_path="app/orders.py",
        max_mutants=20,
    )

    assert report.total_mutants_generated > 0
    assert report.file_path == "app/orders.py"

    op_types = {m.operator_type for m in report.mutants}
    # 验证是否成功覆盖了 ROR (关系反转), LCR (逻辑连接替换), RVO (返回值篡改) 等算子
    assert MutationOperatorType.ROR in op_types
    assert MutationOperatorType.LCR in op_types
    assert MutationOperatorType.RVO in op_types

    # 验证 ROR 变异体描述与代码生成
    ror_mutant = next(m for m in report.mutants if m.operator_type == MutationOperatorType.ROR)
    assert ror_mutant.original_token == ">"
    assert ror_mutant.mutated_token == "<="
    assert "<=" in ror_mutant.mutated_code

    # 验证 LCR 变异体
    lcr_mutant = next(m for m in report.mutants if m.operator_type == MutationOperatorType.LCR)
    assert lcr_mutant.original_token == "and"
    assert lcr_mutant.mutated_token == "or"
    assert " or " in lcr_mutant.mutated_code


def test_generate_mutants_restricted_to_target_lines():
    # 仅限制第 2 行 (即 if price > 1000 and is_vip: 这一行)
    report = generate_code_mutants(
        source_code=SAMPLE_CODE,
        file_path="app/orders.py",
        target_lines=[2],
    )

    assert report.total_mutants_generated > 0
    # 所有生成的变异体行号必须严格等于 2
    for m in report.mutants:
        assert m.line_number == 2


def test_syntax_error_resilience():
    # 传入非法语法代码，应安全返回空报告而非抛出异常
    report = generate_code_mutants(
        source_code="def broken_syntax( {",
        file_path="broken.py",
    )
    assert report.total_mutants_generated == 0
    assert len(report.mutants) == 0


def test_get_and_list_mutants_and_reports():
    report = generate_code_mutants(
        source_code=SAMPLE_CODE,
        file_path="app/orders.py",
    )

    fetched_report = get_mutation_report(report.generation_id)
    assert fetched_report is not None
    assert fetched_report.generation_id == report.generation_id

    reports_list = list_mutation_reports()
    assert len(reports_list) == 1

    first_mutant = report.mutants[0]
    fetched_mutant = get_mutant_by_id(first_mutant.mutant_id)
    assert fetched_mutant is not None
    assert fetched_mutant.mutant_id == first_mutant.mutant_id
