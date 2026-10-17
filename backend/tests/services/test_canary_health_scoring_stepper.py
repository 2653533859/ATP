"""智能金丝雀健康度评分与多阶步进调度器单测 (T2.1)"""

from __future__ import annotations

from app.services.canary_baseline_metric_comparator import (
    CanaryDualTrackComparisonReport,
    MetricDeviationVerdict,
    TrackMetricsSample,
)
from app.services.canary_health_scoring_stepper import (
    CanaryStepStage,
    CanaryStepperAction,
    calculate_canary_health_score,
    evaluate_canary_stepping_schedule,
)


def _make_sample_report(
    error_diff: float = 0.05,
    lat_ratio: float = 1.02,
    success_rate: float = 99.9,
    verdict: MetricDeviationVerdict = MetricDeviationVerdict.CONFORMANT,
) -> CanaryDualTrackComparisonReport:
    base = TrackMetricsSample(
        track_name="baseline",
        version_tag="v1.0.0",
        total_requests=10000,
        error_requests=10,
        error_rate_pct=0.1,
        success_rate_pct=99.9,
        p99_latency_ms=100.0,
        avg_latency_ms=30.0,
    )
    canary = TrackMetricsSample(
        track_name="canary",
        version_tag="v1.1.0",
        total_requests=1000,
        error_requests=int(1000 * (0.1 + error_diff) / 100.0),
        error_rate_pct=0.1 + error_diff,
        success_rate_pct=success_rate,
        p99_latency_ms=100.0 * lat_ratio,
        avg_latency_ms=30.0 * lat_ratio,
    )
    return CanaryDualTrackComparisonReport(
        report_id="rep_test_01",
        target_service="payment-service",
        canary_version="v1.1.0",
        baseline_version="v1.0.0",
        overall_verdict=verdict,
        baseline_metrics=base,
        canary_metrics=canary,
        error_rate_diff_pct=error_diff,
        latency_p99_ratio=lat_ratio,
        cpu_diff_pct=2.0,
        findings=["平稳"],
    )


def test_calculate_canary_health_score_excellent():
    rep = _make_sample_report(error_diff=0.0, lat_ratio=1.01, success_rate=99.95)
    health = calculate_canary_health_score(rep)
    assert health.composite_score >= 95.0
    assert health.grade == "EXCELLENT"
    assert len(health.dimensions) == 5


def test_calculate_canary_health_score_poor():
    rep = _make_sample_report(
        error_diff=3.5,
        lat_ratio=2.2,
        success_rate=94.0,
        verdict=MetricDeviationVerdict.BREACHED_DEFICIT,
    )
    health = calculate_canary_health_score(rep)
    assert health.composite_score < 60.0
    assert health.grade == "POOR"


def test_stepping_hold_observing_on_low_samples():
    rep = _make_sample_report()
    decision = evaluate_canary_stepping_schedule(
        comparison_report=rep,
        current_stage=CanaryStepStage.STAGE_1_5PCT,
        window_requests_accumulated=120,  # 低于 500
    )
    assert decision.recommended_action == CanaryStepperAction.HOLD_OBSERVING
    assert decision.next_recommended_weight_pct == 5.0
    assert "未达到最小观察窗口要求" in decision.evaluation_summary


def test_stepping_promote_to_next_stage():
    rep = _make_sample_report(error_diff=0.0, lat_ratio=1.02)
    decision = evaluate_canary_stepping_schedule(
        comparison_report=rep,
        current_stage=CanaryStepStage.STAGE_1_5PCT,
        window_requests_accumulated=800,
    )
    assert decision.recommended_action == CanaryStepperAction.PROMOTE_NEXT_STAGE
    assert decision.next_recommended_weight_pct == 10.0  # 步进至 10%
    assert "EXCELLENT" in decision.evaluation_summary


def test_stepping_ready_for_full_cutover():
    rep = _make_sample_report(error_diff=0.0, lat_ratio=1.0)
    decision = evaluate_canary_stepping_schedule(
        comparison_report=rep,
        current_stage=CanaryStepStage.STAGE_4_50PCT,  # 已达到 50% 阶梯
        window_requests_accumulated=2000,
    )
    assert decision.recommended_action == CanaryStepperAction.READY_FOR_FULL_CUTOVER
    assert decision.next_recommended_weight_pct == 100.0  # 准予 100% 全量割接
    assert "全量割接" in decision.evaluation_summary


def test_stepping_block_or_freeze_on_poor_health():
    rep = _make_sample_report(
        error_diff=3.0,
        lat_ratio=1.8,
        verdict=MetricDeviationVerdict.BREACHED_DEFICIT,
    )
    decision = evaluate_canary_stepping_schedule(
        comparison_report=rep,
        current_stage=CanaryStepStage.STAGE_2_10PCT,
        window_requests_accumulated=800,
    )
    assert decision.recommended_action == CanaryStepperAction.BLOCK_OR_FREEZE
    assert decision.next_recommended_weight_pct == 10.0

    d = decision.to_dict()
    assert d["recommended_action"] == "BLOCK_OR_FREEZE"
    assert d["health_score"]["composite_score"] < 75.0
