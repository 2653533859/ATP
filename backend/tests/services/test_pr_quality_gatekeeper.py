"""Unit tests for PR Quality Gatekeeper Service (S4.1)."""

from __future__ import annotations

import pytest

from app.services.pr_quality_gatekeeper import (
    MergeGateVerdict,
    evaluate_pr_quality_gate,
    get_pr_gate_report,
    list_pr_gate_reports,
    reset_pr_gate_registry,
)


@pytest.fixture(autouse=True)
def clean_gate_registry():
    reset_pr_gate_registry()
    yield
    reset_pr_gate_registry()


def test_evaluate_pr_gate_approved():
    report = evaluate_pr_quality_gate(
        pr_id="101",
        commit_sha="a1b2c3d4",
        author="alice",
        target_branch="main",
        test_pass_rate_pct=100.0,
        test_failed_cases_count=0,
        risk_score=15.0,
        risk_level="LOW",
        mutation_score_pct=88.5,
    )

    assert report.verdict == MergeGateVerdict.MERGE_APPROVED
    assert report.is_mergeable is True
    assert report.overall_compliance_score == 100.0
    assert len(report.blocking_reasons) == 0
    assert len(report.warning_reasons) == 0


def test_evaluate_pr_gate_blocked_by_test_failure():
    report = evaluate_pr_quality_gate(
        pr_id="102",
        commit_sha="e5f6a7b8",
        author="bob",
        target_branch="main",
        test_pass_rate_pct=95.0,
        test_failed_cases_count=2,
        risk_score=20.0,
        risk_level="LOW",
    )

    assert report.verdict == MergeGateVerdict.MERGE_BLOCKED
    assert report.is_mergeable is False
    assert any("失败用例" in reason for reason in report.blocking_reasons)
    assert len(report.remediation_steps) > 0


def test_evaluate_pr_gate_blocked_by_weak_mutation_score():
    report = evaluate_pr_quality_gate(
        pr_id="103",
        commit_sha="99887766",
        author="charlie",
        test_pass_rate_pct=100.0,
        test_failed_cases_count=0,
        mutation_score_pct=35.0,  # 低于 50% 严重脆弱硬阻断
    )

    assert report.verdict == MergeGateVerdict.MERGE_BLOCKED
    assert report.is_mergeable is False
    assert any("变异得分严重不达标" in reason for reason in report.blocking_reasons)


def test_evaluate_pr_gate_critical_risk_requires_dual_approval():
    # 极高风险但没有双人审批 -> 阻断
    blocked_report = evaluate_pr_quality_gate(
        pr_id="104",
        commit_sha="44556677",
        risk_score=85.0,
        risk_level="CRITICAL",
        has_dual_approvals=False,
    )
    assert blocked_report.verdict == MergeGateVerdict.MERGE_BLOCKED
    assert any("双人签字" in reason for reason in blocked_report.blocking_reasons)

    # 极高风险但具备双人审批 -> 通过
    approved_report = evaluate_pr_quality_gate(
        pr_id="104",
        commit_sha="44556677",
        risk_score=85.0,
        risk_level="CRITICAL",
        has_dual_approvals=True,
    )
    assert approved_report.verdict == MergeGateVerdict.MERGE_APPROVED
    assert approved_report.is_mergeable is True


def test_evaluate_pr_gate_conditional_pass():
    # 变异得分 60% (在 50%~70% 之间，非致命，产生 Warning)
    report = evaluate_pr_quality_gate(
        pr_id="105",
        commit_sha="11223344",
        test_pass_rate_pct=100.0,
        test_failed_cases_count=0,
        mutation_score_pct=60.0,
        min_mutation_score_threshold=70.0,
    )

    assert report.verdict == MergeGateVerdict.CONDITIONAL_PASS
    assert report.is_mergeable is True
    assert len(report.warning_reasons) == 1
    assert len(report.blocking_reasons) == 0


def test_get_and_list_pr_gate_reports():
    report = evaluate_pr_quality_gate(
        pr_id="106",
        commit_sha="00112233",
    )

    fetched = get_pr_gate_report(report.gate_id)
    assert fetched is not None
    assert fetched.gate_id == report.gate_id

    reports = list_pr_gate_reports()
    assert len(reports) == 1
    assert reports[0].gate_id == report.gate_id
