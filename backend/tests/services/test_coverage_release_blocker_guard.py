"""质量门禁发布强阻断与非合规豁免审批看门狗单测 (T4.1)"""

from __future__ import annotations

from app.services.coverage_release_blocker_guard import (
    ReleaseGuardAction,
    enforce_coverage_release_gate,
    is_valid_waiver_token,
)
from app.services.incremental_coverage_gate_evaluator import (
    CoverageGateVerdictAction,
    IncrementalCoverageGateVerdict,
)


def test_is_valid_waiver_token():
    assert is_valid_waiver_token("ATP-COV-WAIVER-20261018-XYZ99") is True
    assert is_valid_waiver_token("INVALID_TOKEN") is False
    assert is_valid_waiver_token("") is False
    assert is_valid_waiver_token(None) is False


def test_enforce_gate_passed_conformant():
    gate_verdict = IncrementalCoverageGateVerdict(
        verdict_id="gate_1",
        diff_report_id="dcov_1",
        is_passed=True,
        action=CoverageGateVerdictAction.PASSED_CONFORMANT,
        actual_diff_line_coverage_pct=92.0,
        target_min_diff_line_coverage_pct=85.0,
        actual_diff_branch_coverage_pct=80.0,
        target_min_diff_branch_coverage_pct=70.0,
        p0_uncovered_count=0,
        uncovered_lines_count=2,
        breached_rules=[],
        remediation_suggestions=[],
    )

    verdict = enforce_coverage_release_gate(
        pipeline_id="pipe_build_101",
        environment="production",
        gate_verdict=gate_verdict,
    )
    assert verdict.is_blocked is False
    assert verdict.action == ReleaseGuardAction.ALLOW_RELEASE_CONFORMANT
    assert "准予放行发布" in verdict.reasons[0]


def test_enforce_gate_blocked_without_waiver():
    gate_verdict = IncrementalCoverageGateVerdict(
        verdict_id="gate_2",
        diff_report_id="dcov_2",
        is_passed=False,
        action=CoverageGateVerdictAction.BLOCKED_DEFICIT,
        actual_diff_line_coverage_pct=60.0,
        target_min_diff_line_coverage_pct=85.0,
        actual_diff_branch_coverage_pct=50.0,
        target_min_diff_branch_coverage_pct=70.0,
        p0_uncovered_count=1,
        uncovered_lines_count=10,
        breached_rules=["存在 1 处 P0 阻塞级高危未覆盖分支"],
        remediation_suggestions=["增补测试用例"],
    )

    verdict = enforce_coverage_release_gate(
        pipeline_id="pipe_build_102",
        environment="production",
        gate_verdict=gate_verdict,
    )
    assert verdict.is_blocked is True
    assert verdict.action == ReleaseGuardAction.BLOCKED_DEFICIT_NO_WAIVER
    assert len(verdict.reasons) >= 1


def test_enforce_gate_blocked_with_invalid_waiver():
    gate_verdict = IncrementalCoverageGateVerdict(
        verdict_id="gate_3",
        diff_report_id="dcov_3",
        is_passed=False,
        action=CoverageGateVerdictAction.BLOCKED_DEFICIT,
        actual_diff_line_coverage_pct=70.0,
        target_min_diff_line_coverage_pct=85.0,
        actual_diff_branch_coverage_pct=60.0,
        target_min_diff_branch_coverage_pct=70.0,
        p0_uncovered_count=0,
        uncovered_lines_count=5,
        breached_rules=["增量代码行覆盖率未达标"],
        remediation_suggestions=[],
    )

    # 携带了非白名单审批人以及非法令牌的豁免单
    verdict = enforce_coverage_release_gate(
        pipeline_id="pipe_build_103",
        environment="production",
        gate_verdict=gate_verdict,
        waiver_ticket_id="INVALID-TICKET-01",
        approved_by="unauthorized_dev@external.com",
        waiver_token="SHORT",
        remediation_deadline="",
    )
    assert verdict.is_blocked is True
    assert verdict.action == ReleaseGuardAction.BLOCKED_INVALID_WAIVER
    assert "合规校验未通过" in verdict.reasons[0]


def test_enforce_gate_allowed_with_valid_emergency_waiver():
    gate_verdict = IncrementalCoverageGateVerdict(
        verdict_id="gate_4",
        diff_report_id="dcov_4",
        is_passed=False,
        action=CoverageGateVerdictAction.BLOCKED_DEFICIT,
        actual_diff_line_coverage_pct=78.0,
        target_min_diff_line_coverage_pct=85.0,
        actual_diff_branch_coverage_pct=65.0,
        target_min_diff_branch_coverage_pct=70.0,
        p0_uncovered_count=0,
        uncovered_lines_count=4,
        breached_rules=["增量覆盖率未达标"],
        remediation_suggestions=["在下一迭代前补齐测试"],
    )

    # 携带完整合规三要素的特批豁免单
    verdict = enforce_coverage_release_gate(
        pipeline_id="pipe_hotfix_202",
        environment="production",
        gate_verdict=gate_verdict,
        waiver_ticket_id="WAIVER-HOTFIX-20261018-009",
        approved_by="qa_director@atp.io",
        waiver_token="ATP-COV-WAIVER-20261018-AUTH9988",
        remediation_deadline="2026-10-25 18:00:00",
    )
    assert verdict.is_blocked is False
    assert verdict.action == ReleaseGuardAction.ALLOW_RELEASE_WAIVED
    assert "特批放行" in verdict.reasons[0]
    assert verdict.waiver_ticket_id == "WAIVER-HOTFIX-20261018-009"

    d = verdict.to_dict()
    assert d["action"] == "ALLOW_RELEASE_WAIVED"
    assert d["is_blocked"] is False
