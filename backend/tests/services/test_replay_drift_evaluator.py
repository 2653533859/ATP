"""回放偏离评分与 Breaking Change 裁决控制器单测 (T2.3)"""

from __future__ import annotations

from app.services.dynamic_noise_suppressor import SuppressedDiffReport
from app.services.replay_drift_evaluator import (
    ChangeImpactLevel,
    ReplayVerdict,
    evaluate_replay_drift,
)
from app.services.traffic_response_diff_comparator import (
    DiffSeverity,
    ResponseDiffCategory,
    ResponseDiffItem,
)


def test_evaluate_perfect_match():
    report = SuppressedDiffReport(
        report_id="sup_1",
        record_id="rec_1",
        original_diff_count=2,
        suppressed_noise_count=2,
        effective_diff_count=0,
        has_effective_breaking=False,
        effective_diffs=[],
        noise_diffs=[],
        applied_rule_ids=[],
    )

    res = evaluate_replay_drift(report)
    assert res.consistency_score == 100.0
    assert res.impact_level == ChangeImpactLevel.NONE
    assert res.verdict == ReplayVerdict.PASSED
    assert res.is_deployable is True
    assert len(res.blocker_reasons) == 0


def test_evaluate_breaking_status_code_mismatch():
    diff = ResponseDiffItem(
        diff_id="d_sc",
        category=ResponseDiffCategory.STATUS_CODE_MISMATCH,
        severity=DiffSeverity.BLOCKER,
        json_path="$.status_code",
        baseline_value=200,
        replayed_value=500,
        message="500 Internal Error",
    )
    report = SuppressedDiffReport(
        report_id="sup_2",
        record_id="rec_2",
        original_diff_count=1,
        suppressed_noise_count=0,
        effective_diff_count=1,
        has_effective_breaking=True,
        effective_diffs=[diff],
        noise_diffs=[],
        applied_rule_ids=[],
    )

    res = evaluate_replay_drift(report)
    assert res.consistency_score == 50.0
    assert res.impact_level == ChangeImpactLevel.BREAKING
    assert res.verdict == ReplayVerdict.BLOCKED_BREAKING
    assert res.is_deployable is False
    assert len(res.blocker_reasons) == 1


def test_evaluate_missing_key_breaking():
    diff = ResponseDiffItem(
        diff_id="d_k",
        category=ResponseDiffCategory.MISSING_KEY,
        severity=DiffSeverity.MAJOR,
        json_path="$.data.order_id",
        baseline_value="OD_123",
        replayed_value=None,
        message="missing order_id",
    )
    report = SuppressedDiffReport(
        report_id="sup_3",
        record_id="rec_3",
        original_diff_count=1,
        suppressed_noise_count=0,
        effective_diff_count=1,
        has_effective_breaking=True,
        effective_diffs=[diff],
        noise_diffs=[],
        applied_rule_ids=[],
    )

    res = evaluate_replay_drift(report)
    assert res.consistency_score == 80.0
    assert res.impact_level == ChangeImpactLevel.BREAKING
    assert res.verdict == ReplayVerdict.BLOCKED_BREAKING
    assert res.is_deployable is False


def test_evaluate_non_breaking_permissive():
    diff_val = ResponseDiffItem(
        diff_id="d_v",
        category=ResponseDiffCategory.VALUE_MISMATCH,
        severity=DiffSeverity.MINOR,
        json_path="$.data.desc",
        baseline_value="旧描述",
        replayed_value="新描述",
        message="desc updated",
    )
    diff_extra = ResponseDiffItem(
        diff_id="d_e",
        category=ResponseDiffCategory.UNEXPECTED_KEY,
        severity=DiffSeverity.INFO,
        json_path="$.data.tag",
        baseline_value=None,
        replayed_value="new_tag",
        message="extra tag",
    )
    report = SuppressedDiffReport(
        report_id="sup_4",
        record_id="rec_4",
        original_diff_count=2,
        suppressed_noise_count=0,
        effective_diff_count=2,
        has_effective_breaking=False,
        effective_diffs=[diff_val, diff_extra],
        noise_diffs=[],
        applied_rule_ids=[],
    )

    res = evaluate_replay_drift(report)
    # 100 - 5 (value) - 2 (extra) = 93.0
    assert res.consistency_score == 93.0
    assert res.impact_level == ChangeImpactLevel.NON_BREAKING
    assert res.verdict == ReplayVerdict.WARN_PERMISSIVE
    assert res.is_deployable is True
    assert len(res.blocker_reasons) == 0

    d = res.to_dict()
    assert d["verdict"] == "WARN_PERMISSIVE"
    assert d["consistency_score"] == 93.0
