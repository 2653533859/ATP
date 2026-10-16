"""Unit tests for Mutation Execution Runner Service (S3.2)."""

from __future__ import annotations

import pytest

from app.services.code_mutation_operator_engine import (
    generate_code_mutants,
    reset_mutation_registry,
)
from app.services.mutation_execution_runner import (
    MutantStatus,
    get_mutation_execution_report,
    list_mutation_execution_reports,
    reset_mutation_execution_registry,
    run_mutation_execution,
)


@pytest.fixture(autouse=True)
def clean_mutation_execution():
    reset_mutation_registry()
    reset_mutation_execution_registry()
    yield
    reset_mutation_registry()
    reset_mutation_execution_registry()


SOURCE_CODE = """def multiply(a: int, b: int) -> int:
    return a * b
"""


def test_mutation_execution_killed():
    # 生成变异体：如 * 变更为 // (AOR)
    gen_report = generate_code_mutants(SOURCE_CODE, file_path="math.py")
    assert len(gen_report.mutants) > 0

    mutant = gen_report.mutants[0]

    # 具备严密断言的测试用例
    def test_multiply_strong_assertion(scope):
        fn = scope["multiply"]
        assert fn(3, 4) == 12, "3 * 4 must equal 12"

    test_cases = [
        {
            "case_id": 101,
            "case_name": "乘法严密断言测试",
            "test_fn": test_multiply_strong_assertion,
        }
    ]

    report = run_mutation_execution(mutants=[mutant], test_cases=test_cases)
    assert report.total_mutants_tested == 1
    assert report.killed_count == 1
    assert report.survived_count == 0
    assert report.kill_rate_pct == 100.0

    res = report.results[0]
    assert res.status == MutantStatus.KILLED
    assert res.killing_test_case_id == 101
    assert res.killing_test_case_name == "乘法严密断言测试"


def test_mutation_execution_survived_when_assertion_missing():
    gen_report = generate_code_mutants(SOURCE_CODE, file_path="math.py")
    assert len(gen_report.mutants) > 0
    mutant = gen_report.mutants[0]

    # 脆弱用例：仅执行但未做有效校验（例如断言总是 True 或断言不相关逻辑）
    def test_weak_without_assertion(scope):
        fn = scope["multiply"]
        _ = fn(3, 4)  # 只调用，无断言！
        assert True

    test_cases = [
        {
            "case_id": 102,
            "case_name": "脆弱无断言用例",
            "test_fn": test_weak_without_assertion,
        }
    ]

    report = run_mutation_execution(mutants=[mutant], test_cases=test_cases)
    assert report.total_mutants_tested == 1
    assert report.killed_count == 0
    assert report.survived_count == 1
    assert report.kill_rate_pct == 0.0

    res = report.results[0]
    assert res.status == MutantStatus.SURVIVED
    assert res.killing_test_case_id is None
    assert mutant.mutant_id in report.survived_mutant_ids


def test_get_and_list_mutation_execution_reports():
    gen_report = generate_code_mutants(SOURCE_CODE, file_path="math.py")
    report = run_mutation_execution(mutants=gen_report.mutants[:1], test_cases=[])

    fetched = get_mutation_execution_report(report.run_id)
    assert fetched is not None
    assert fetched.run_id == report.run_id

    reports = list_mutation_execution_reports()
    assert len(reports) == 1
    assert reports[0].run_id == report.run_id
