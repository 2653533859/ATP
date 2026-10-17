"""架构韧性弱点雷达分析与加固建议生成器单测 (T2.3)"""

from __future__ import annotations

from app.services.architecture_weakness_radar import (
    HardeningActionType,
    analyze_architecture_resilience_radar,
)
from app.services.chaos_blast_radius_controller import BlastControllerVerdict, BlastTripAction
from app.services.resilience_rto_evaluator import ResilienceGrade, ResilienceRTOEvaluation


def test_analyze_radar_excellent_system():
    # 卓越架构：毫秒级熔断、100% 降级、秒级自愈、未触碰爆炸半径红线
    rto_eval = ResilienceRTOEvaluation(
        evaluation_id="eval_exc",
        experiment_id="exp_pay",
        target_service="order-service",
        circuit_breaker_trip_time_ms=180.0,
        fallback_takeover_rate_pct=100.0,
        recovery_time_objective_seconds=2.0,
        recovery_point_objective_seconds=0.0,
        resilience_grade=ResilienceGrade.GRADE_A_RESILIENT,
        is_slo_compliant=True,
    )
    blast_verdict = BlastControllerVerdict(
        experiment_id="exp_pay",
        is_tripped=False,
        action=BlastTripAction.SAFE_CONTAINED,
        tripped_rules=[],
    )

    report = analyze_architecture_resilience_radar(
        rto_evaluation=rto_eval,
        blast_verdict=blast_verdict,
        steady_violations=[],
    )

    assert report.composite_resilience_score >= 90.0
    assert report.identified_weaknesses_count == 0
    assert len(report.recommendations) == 0
    assert len(report.radar_dimensions) == 5

    d = report.to_dict()
    assert d["composite_resilience_score"] >= 90.0
    assert "fault_isolation" in d["dimension_scores"]


def test_analyze_radar_weak_system_generates_recommendations():
    # 脆弱架构：断路器严重超时、降级率仅 40%、自愈耗时 30 秒、触发爆炸半径熔断、有稳态违规
    rto_eval = ResilienceRTOEvaluation(
        evaluation_id="eval_weak",
        experiment_id="exp_legacy_pay",
        target_service="payment-gateway",
        circuit_breaker_trip_time_ms=3500.0,  # 严重迟缓
        fallback_takeover_rate_pct=40.0,  # 降级不力
        recovery_time_objective_seconds=30.0,  # 自愈恢复过长
        recovery_point_objective_seconds=5.0,
        resilience_grade=ResilienceGrade.GRADE_D_VULNERABLE,
        is_slo_compliant=False,
    )
    blast_verdict = BlastControllerVerdict(
        experiment_id="exp_legacy_pay",
        is_tripped=True,
        action=BlastTripAction.EMERGENCY_ABORT,
        tripped_rules=["错误率击穿熔断红线: 15.0% > 5.0%"],
        teardown_actions_executed=["teardown"],
    )

    report = analyze_architecture_resilience_radar(
        rto_evaluation=rto_eval,
        blast_verdict=blast_verdict,
        steady_violations=["p99 延迟击穿基线", "成功率低于 99%"],
    )

    assert report.composite_resilience_score < 70.0
    assert report.identified_weaknesses_count == 4
    assert len(report.recommendations) == 4

    rec_types = {r.action_type for r in report.recommendations}
    assert HardeningActionType.CIRCUIT_BREAKER_TUNING in rec_types
    assert HardeningActionType.CACHE_FALLBACK_STRENGTHEN in rec_types
    assert HardeningActionType.BULKHEAD_ISOLATION in rec_types
    assert HardeningActionType.EXPONENTIAL_BACKOFF_RETRY in rec_types

    d = report.to_dict()
    assert len(d["recommendations"]) == 4
    assert d["identified_weaknesses_count"] == 4
