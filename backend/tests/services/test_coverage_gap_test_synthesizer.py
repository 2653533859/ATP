"""缺失用例场景反向合成与测试输入推导器单测 (T2.2)"""

from __future__ import annotations

from app.services.coverage_gap_test_synthesizer import (
    _deduce_boundary_inputs_from_condition,
    synthesize_coverage_gap_test_cases,
)
from app.services.uncovered_branch_risk_analyzer import (
    BranchRiskSeverity,
    UncoveredBranchAnalysisReport,
    UncoveredBranchCategory,
    UncoveredBranchItem,
)


def test_deduce_boundary_inputs_payment():
    inputs, assertions, mocks = _deduce_boundary_inputs_from_condition(
        condition_expr="if amount <= 0:",
        category=UncoveredBranchCategory.PAYMENT_FINANCIAL,
    )
    assert inputs["amount"] == -10.0
    assert "400" in assertions
    assert any("payment_gateway" in m for m in mocks)

    inputs_gt, _, _ = _deduce_boundary_inputs_from_condition(
        condition_expr="if amount > 500:",
        category=UncoveredBranchCategory.PAYMENT_FINANCIAL,
    )
    assert inputs_gt["amount"] == 501.0


def test_deduce_boundary_inputs_auth():
    inputs, assertions, mocks = _deduce_boundary_inputs_from_condition(
        condition_expr="if not token:",
        category=UncoveredBranchCategory.AUTH_SECURITY,
    )
    assert inputs["authorization_header"] is None
    assert "401" in assertions
    assert any("auth_service" in m for m in mocks)


def test_deduce_boundary_inputs_circuit_breaker():
    inputs, assertions, mocks = _deduce_boundary_inputs_from_condition(
        condition_expr="if circuit_state == OPEN:",
        category=UncoveredBranchCategory.CIRCUIT_BREAKER_FALLBACK,
    )
    assert inputs["simulate_downstream_latency_ms"] >= 1000
    assert "is_fallback" in assertions
    assert any("circuit_breaker" in m for m in mocks)


def test_synthesize_coverage_gap_plan():
    branch_1 = UncoveredBranchItem(
        branch_id="br_pay_01",
        file_path="backend/services/payment.py",
        line_start=15,
        line_end=17,
        code_snippet="if amount <= 0:\n    raise InvalidAmountException()",
        category=UncoveredBranchCategory.PAYMENT_FINANCIAL,
        severity=BranchRiskSeverity.P0_BLOCKING,
        reason="资金敏感",
        condition_expr="if amount <= 0:",
        consequence_summary="非法金额漏检",
    )
    branch_2 = UncoveredBranchItem(
        branch_id="br_auth_02",
        file_path="backend/services/auth.py",
        line_start=30,
        line_end=32,
        code_snippet="if not token:\n    return 401",
        category=UncoveredBranchCategory.AUTH_SECURITY,
        severity=BranchRiskSeverity.P0_BLOCKING,
        reason="安全鉴权",
        condition_expr="if not token:",
        consequence_summary="鉴权绕过",
    )

    uncovered_report = UncoveredBranchAnalysisReport(
        report_id="ubr_test_01",
        diff_report_id="dcov_test_01",
        total_uncovered_branches=2,
        p0_count=2,
        p1_count=0,
        p2_count=0,
        branches=[branch_1, branch_2],
        is_release_blocked=True,
    )

    plan = synthesize_coverage_gap_test_cases(uncovered_report)
    assert plan.total_synthesized_cases == 2
    assert plan.p0_cases_count == 2
    assert plan.estimated_coverage_gain_pct > 0.0

    draft_1 = plan.cases[0]
    assert draft_1.file_path == "backend/services/payment.py"
    assert "test_cover_payment_financial" in draft_1.suggested_test_code
    assert "InvalidAmount" in draft_1.expected_assertion

    draft_2 = plan.cases[1]
    assert draft_2.recommended_inputs["authorization_header"] is None

    d = plan.to_dict()
    assert d["total_synthesized_cases"] == 2
    assert len(d["cases"]) == 2
