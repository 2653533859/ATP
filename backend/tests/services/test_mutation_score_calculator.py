"""Unit tests for Mutation Score Calculator Service (S3.3)."""

from __future__ import annotations

import pytest

from app.services.code_mutation_operator_engine import (
    generate_code_mutants,
    reset_mutation_registry,
)
from app.services.mutation_execution_runner import (
    MutantExecutionResult,
    MutantStatus,
    reset_mutation_execution_registry,
    run_mutation_execution,
)
from app.services.mutation_score_calculator import (
    AssertionAdequacyLevel,
    calculate_mutation_score,
    get_mutation_score_report,
    list_mutation_score_reports,
    reset_mutation_score_registry,
)


@pytest.fixture(autouse=True)
def clean_all_registries():
    reset_mutation_registry()
    reset_mutation_execution_registry()
    reset_mutation_score_registry()
    yield
    reset_mutation_registry()
    reset_mutation_execution_registry()
    reset_mutation_score_registry()


SAMPLE_CODE = """def checkout_discount(total: float) -> float:
    if total > 500:
        return total * 0.9
    return total
"""


def test_calculate_mutation_score_excellent():
    # 模拟 4 个变异体全部被杀死 (100% 捕获)
    results = [
        MutantExecutionResult(
            mutant_id="mut_1",
            status=MutantStatus.KILLED,
            killing_test_case_id=1,
            killing_test_case_name="用例1",
            execution_duration_ms=10.0,
            error_message="AssertionError",
            line_number=2,
            operator_type="ROR",
            description="关系反转",
        ),
        MutantExecutionResult(
            mutant_id="mut_2",
            status=MutantStatus.KILLED,
            killing_test_case_id=2,
            killing_test_case_name="用例2",
            execution_duration_ms=12.0,
            error_message="AssertionError",
            line_number=3,
            operator_type="RVO",
            description="返回值篡改",
        ),
    ]

    report = calculate_mutation_score(execution_results=results)
    assert report.total_mutants == 2
    assert report.killed_count == 2
    assert report.survived_count == 0
    assert report.mutation_score_pct == 100.0
    assert report.adequacy_level == AssertionAdequacyLevel.EXCELLENT
    assert len(report.blindspots) == 0

    # 验证算子层面的捕获统计
    assert "ROR" in report.operator_breakdowns
    assert report.operator_breakdowns["ROR"].operator_mutation_score_pct == 100.0


def test_calculate_mutation_score_weak_and_blindspots():
    # 模拟 1 个杀死，3 个存活 (变异得分 25%，评定为 WEAK)
    results = [
        MutantExecutionResult(
            mutant_id="mut_1",
            status=MutantStatus.KILLED,
            killing_test_case_id=1,
            killing_test_case_name="用例1",
            execution_duration_ms=10.0,
            error_message="AssertionError",
            line_number=2,
            operator_type="ROR",
            description="关系反转",
        ),
        MutantExecutionResult(
            mutant_id="mut_2",
            status=MutantStatus.SURVIVED,
            killing_test_case_id=None,
            killing_test_case_name=None,
            execution_duration_ms=8.0,
            error_message=None,
            line_number=3,
            operator_type="RVO",
            description="返回值篡改",
        ),
        MutantExecutionResult(
            mutant_id="mut_3",
            status=MutantStatus.SURVIVED,
            killing_test_case_id=None,
            killing_test_case_name=None,
            execution_duration_ms=9.0,
            error_message=None,
            line_number=2,
            operator_type="BVO",
            description="边界常数偏移",
        ),
        MutantExecutionResult(
            mutant_id="mut_4",
            status=MutantStatus.SURVIVED,
            killing_test_case_id=None,
            killing_test_case_name=None,
            execution_duration_ms=9.0,
            error_message=None,
            line_number=2,
            operator_type="LCR",
            description="逻辑连接符替换",
        ),
    ]

    report = calculate_mutation_score(execution_results=results)
    assert report.total_mutants == 4
    assert report.killed_count == 1
    assert report.survived_count == 3
    assert report.mutation_score_pct == 25.0
    assert report.adequacy_level == AssertionAdequacyLevel.WEAK

    # 验证断言盲区
    assert len(report.blindspots) == 3
    rvo_blindspot = next(b for b in report.blindspots if b.operator_type == "RVO")
    assert "返回值" in rvo_blindspot.suggested_assertion_fix


def test_integration_with_mutation_runner():
    # 端到端串联：生成变异体 -> 执行检验 -> 计算得分
    gen_report = generate_code_mutants(SAMPLE_CODE, file_path="app/orders.py")
    assert len(gen_report.mutants) > 0

    def strong_test(scope):
        fn = scope["checkout_discount"]
        assert fn(600) == 540.0, "Discount calculation must equal 540"

    run_report = run_mutation_execution(
        mutants=gen_report.mutants,
        test_cases=[{"case_id": 1, "case_name": "强断言测试", "test_fn": strong_test}],
    )

    # 依据 run_id 自动计算变异得分
    score_report = calculate_mutation_score(execution_run_id=run_report.run_id)
    assert score_report.total_mutants == run_report.total_mutants_tested
    assert score_report.execution_run_id == run_report.run_id
    assert score_report.mutation_score_pct >= 0.0


def test_get_and_list_score_reports():
    report = calculate_mutation_score(execution_results=[])
    fetched = get_mutation_score_report(report.score_id)
    assert fetched is not None
    assert fetched.score_id == report.score_id

    reports = list_mutation_score_reports()
    assert len(reports) == 1
    assert reports[0].score_id == report.score_id
