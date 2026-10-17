"""增量覆盖率发布准入卡点与红线裁决器单测 (T2.3)"""

from __future__ import annotations

from app.services.diff_coverage_staining_engine import (
    DiffCoverageReport,
    FileDiffCoverageStaining,
)
from app.services.incremental_coverage_gate_evaluator import (
    CoverageGateVerdictAction,
    IncrementalCoverageGatePolicy,
    _is_file_exempt,
    evaluate_incremental_coverage_gate,
)
from app.services.uncovered_branch_risk_analyzer import (
    BranchRiskSeverity,
    UncoveredBranchAnalysisReport,
    UncoveredBranchCategory,
    UncoveredBranchItem,
)


def test_is_file_exempt():
    exempt_patterns = ["tests/*", "*.spec.ts", "alembic/*"]
    assert _is_file_exempt("tests/services/test_api.py", exempt_patterns) is True
    assert _is_file_exempt("frontend/src/views/MyView.spec.ts", exempt_patterns) is True
    assert _is_file_exempt("backend/app/services/payment.py", exempt_patterns) is False


def test_evaluate_gate_passed_conformant():
    file_staining = FileDiffCoverageStaining(
        file_path="backend/app/services/order.py",
        changed_executable_lines_count=10,
        changed_covered_lines_count=10,
        changed_uncovered_lines_count=0,
        changed_partial_lines_count=0,
        diff_line_coverage_pct=100.0,
        changed_branches_total=2,
        changed_branches_covered=2,
        diff_branch_coverage_pct=100.0,
    )
    diff_report = DiffCoverageReport(
        diff_report_id="dcov_pass",
        base_commit="main",
        target_commit="head",
        total_changed_files=1,
        overall_diff_line_coverage_pct=100.0,
        overall_diff_branch_coverage_pct=100.0,
        files={"backend/app/services/order.py": file_staining},
        total_changed_lines=10,
        total_uncovered_lines=0,
    )

    verdict = evaluate_incremental_coverage_gate(diff_report)
    assert verdict.is_passed is True
    assert verdict.action == CoverageGateVerdictAction.PASSED_CONFORMANT
    assert len(verdict.breached_rules) == 0
    assert verdict.p0_uncovered_count == 0


def test_evaluate_gate_blocked_due_to_p0_uncovered():
    # 覆盖率虽然高达 90%，但漏测了 1 个核心支付 P0 分支
    file_staining = FileDiffCoverageStaining(
        file_path="backend/app/services/payment.py",
        changed_executable_lines_count=10,
        changed_covered_lines_count=9,
        changed_uncovered_lines_count=1,
        changed_partial_lines_count=0,
        diff_line_coverage_pct=90.0,
        changed_branches_total=2,
        changed_branches_covered=2,
        diff_branch_coverage_pct=100.0,
    )
    diff_report = DiffCoverageReport(
        diff_report_id="dcov_p0",
        base_commit="main",
        target_commit="head",
        total_changed_files=1,
        overall_diff_line_coverage_pct=90.0,
        overall_diff_branch_coverage_pct=100.0,
        files={"backend/app/services/payment.py": file_staining},
        total_changed_lines=10,
        total_uncovered_lines=1,
    )
    p0_branch = UncoveredBranchItem(
        branch_id="br_pay_01",
        file_path="backend/app/services/payment.py",
        line_start=20,
        line_end=22,
        code_snippet="refund_payment()",
        category=UncoveredBranchCategory.PAYMENT_FINANCIAL,
        severity=BranchRiskSeverity.P0_BLOCKING,
        reason="资金退款",
        condition_expr="if status == REFUND:",
        consequence_summary="退款资金风险",
    )
    uncovered_analysis = UncoveredBranchAnalysisReport(
        report_id="ubr_1",
        diff_report_id="dcov_p0",
        total_uncovered_branches=1,
        p0_count=1,
        p1_count=0,
        p2_count=0,
        branches=[p0_branch],
        is_release_blocked=True,
    )

    verdict = evaluate_incremental_coverage_gate(
        diff_coverage_report=diff_report,
        uncovered_analysis=uncovered_analysis,
    )
    assert verdict.is_passed is False
    assert verdict.action == CoverageGateVerdictAction.BLOCKED_DEFICIT
    assert any("P0 阻塞级高危未覆盖分支" in r for r in verdict.breached_rules)


def test_evaluate_gate_blocked_due_to_low_line_coverage():
    file_staining = FileDiffCoverageStaining(
        file_path="backend/app/services/auth.py",
        changed_executable_lines_count=10,
        changed_covered_lines_count=5,
        changed_uncovered_lines_count=5,
        changed_partial_lines_count=0,
        diff_line_coverage_pct=50.0,
        changed_branches_total=0,
        changed_branches_covered=0,
        diff_branch_coverage_pct=100.0,
    )
    diff_report = DiffCoverageReport(
        diff_report_id="dcov_low",
        base_commit="main",
        target_commit="head",
        total_changed_files=1,
        overall_diff_line_coverage_pct=50.0,
        overall_diff_branch_coverage_pct=100.0,
        files={"backend/app/services/auth.py": file_staining},
        total_changed_lines=10,
        total_uncovered_lines=5,
    )

    policy = IncrementalCoverageGatePolicy(min_diff_line_coverage_pct=85.0)
    verdict = evaluate_incremental_coverage_gate(diff_report, policy=policy)
    assert verdict.is_passed is False
    assert verdict.action == CoverageGateVerdictAction.BLOCKED_DEFICIT
    assert any("低于准入基准线" in r for r in verdict.breached_rules)


def test_evaluate_gate_warning_conditional():
    # 82.0% 位于 [80%, 85%) 容差预警区间，无 P0 未覆盖分支
    file_staining = FileDiffCoverageStaining(
        file_path="backend/app/services/notify.py",
        changed_executable_lines_count=100,
        changed_covered_lines_count=82,
        changed_uncovered_lines_count=10,
        changed_partial_lines_count=8,
        diff_line_coverage_pct=82.0,
        changed_branches_total=0,
        changed_branches_covered=0,
        diff_branch_coverage_pct=100.0,
    )
    diff_report = DiffCoverageReport(
        diff_report_id="dcov_warn",
        base_commit="main",
        target_commit="head",
        total_changed_files=1,
        overall_diff_line_coverage_pct=82.0,
        overall_diff_branch_coverage_pct=100.0,
        files={"backend/app/services/notify.py": file_staining},
        total_changed_lines=100,
        total_uncovered_lines=10,
    )

    verdict = evaluate_incremental_coverage_gate(diff_report)
    assert verdict.is_passed is True
    assert verdict.action == CoverageGateVerdictAction.WARNING_CONDITIONAL

    d = verdict.to_dict()
    assert d["action"] == "WARNING_CONDITIONAL"
    assert d["is_passed"] is True
