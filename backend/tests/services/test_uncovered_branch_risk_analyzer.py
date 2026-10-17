"""未覆盖高危分支路径漏洞挖掘器单测 (T2.1)"""

from __future__ import annotations

from app.services.diff_coverage_staining_engine import (
    DiffCoverageReport,
    FileDiffCoverageStaining,
)
from app.services.uncovered_branch_risk_analyzer import (
    BranchRiskSeverity,
    UncoveredBranchCategory,
    analyze_uncovered_branch_risks,
)


def test_analyze_uncovered_payment_branch_triggers_p0():
    # 模拟支付扣款未覆盖分支
    file_staining = FileDiffCoverageStaining(
        file_path="app/payment.py",
        changed_executable_lines_count=5,
        changed_covered_lines_count=3,
        changed_uncovered_lines_count=2,
        changed_partial_lines_count=0,
        diff_line_coverage_pct=60.0,
        changed_branches_total=2,
        changed_branches_covered=1,
        diff_branch_coverage_pct=50.0,
        red_uncovered_lines=[10, 11],
    )
    diff_report = DiffCoverageReport(
        diff_report_id="dcov_1",
        base_commit="main",
        target_commit="feat",
        total_changed_files=1,
        overall_diff_line_coverage_pct=60.0,
        overall_diff_branch_coverage_pct=50.0,
        files={"app/payment.py": file_staining},
        total_changed_lines=5,
        total_uncovered_lines=2,
    )
    source_files = {
        "app/payment.py": (
            "def checkout(user, amount):\n"
            "    if amount > 1000:\n"
            "        discount_fee = amount * 0.1\n"
            "        total = amount - discount_fee\n"
            "        charge_wallet(user, total)\n"
            "    return True\n"
            "    # padding\n"
            "    # padding\n"
            "    if user.has_balance:\n"
            "        deduct_charge(user, amount)\n"
            "        record_refund_audit()\n"
        )
    }

    report = analyze_uncovered_branch_risks(diff_report, source_files=source_files)
    assert report.total_uncovered_branches == 1
    assert report.p0_count == 1
    assert report.is_release_blocked is True

    branch = report.branches[0]
    assert branch.line_start == 10
    assert branch.line_end == 11
    assert branch.category == UncoveredBranchCategory.PAYMENT_FINANCIAL
    assert branch.severity == BranchRiskSeverity.P0_BLOCKING
    assert "资金敏感" in branch.reason


def test_analyze_uncovered_auth_and_exception_branches():
    file_staining = FileDiffCoverageStaining(
        file_path="app/auth.py",
        changed_executable_lines_count=6,
        changed_covered_lines_count=3,
        changed_uncovered_lines_count=3,
        changed_partial_lines_count=0,
        diff_line_coverage_pct=50.0,
        changed_branches_total=2,
        changed_branches_covered=1,
        diff_branch_coverage_pct=50.0,
        red_uncovered_lines=[3, 7],
    )
    diff_report = DiffCoverageReport(
        diff_report_id="dcov_2",
        base_commit="main",
        target_commit="feat",
        total_changed_files=1,
        overall_diff_line_coverage_pct=50.0,
        overall_diff_branch_coverage_pct=50.0,
        files={"app/auth.py": file_staining},
        total_changed_lines=6,
        total_uncovered_lines=2,
    )
    source_files = {
        "app/auth.py": (
            "def check_access(token):\n"
            "    if not token:\n"
            "        return unauthorized_permission_denied()\n"
            "    user = get_user(token)\n"
            "    try:\n"
            "        do_action()\n"
            "    except DatabaseException:\n"
            "        rollback_transaction()\n"
        )
    }

    report = analyze_uncovered_branch_risks(diff_report, source_files=source_files)
    assert report.total_uncovered_branches == 2

    # 分支 1 (行 3): 权限拦截未覆盖 (P0)
    b_auth = next(b for b in report.branches if b.line_start == 3)
    assert b_auth.category == UncoveredBranchCategory.AUTH_SECURITY
    assert b_auth.severity == BranchRiskSeverity.P0_BLOCKING

    # 分支 2 (行 7): 异常回滚未覆盖 (P1)
    b_exc = next(b for b in report.branches if b.line_start == 7)
    assert b_exc.category == UncoveredBranchCategory.EXCEPTION_ROLLBACK
    assert b_exc.severity == BranchRiskSeverity.P1_CRITICAL

    d = report.to_dict()
    assert d["p0_count"] >= 1
    assert d["is_release_blocked"] is True


def test_analyze_clean_diff_with_no_uncovered():
    file_staining = FileDiffCoverageStaining(
        file_path="app/clean.py",
        changed_executable_lines_count=4,
        changed_covered_lines_count=4,
        changed_uncovered_lines_count=0,
        changed_partial_lines_count=0,
        diff_line_coverage_pct=100.0,
        changed_branches_total=0,
        changed_branches_covered=0,
        diff_branch_coverage_pct=100.0,
        red_uncovered_lines=[],
        yellow_partial_lines=[],
    )
    diff_report = DiffCoverageReport(
        diff_report_id="dcov_clean",
        base_commit="main",
        target_commit="feat",
        total_changed_files=1,
        overall_diff_line_coverage_pct=100.0,
        overall_diff_branch_coverage_pct=100.0,
        files={"app/clean.py": file_staining},
        total_changed_lines=4,
        total_uncovered_lines=0,
    )

    report = analyze_uncovered_branch_risks(diff_report)
    assert report.total_uncovered_branches == 0
    assert report.p0_count == 0
    assert report.is_release_blocked is False
