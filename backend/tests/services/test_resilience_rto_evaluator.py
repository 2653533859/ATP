"""服务降级与熔断恢复时间 RTO/RPO 评估器单测 (T2.1)"""

from __future__ import annotations

from app.services.resilience_rto_evaluator import (
    ResilienceGrade,
    evaluate_resilience_rto_rpo,
)


def test_evaluate_grade_a_resilience():
    # 模拟卓越韧性: 故障注入 100.0, 熔断触发 100.25 (250ms), 故障移除 110.0, 恢复稳态 112.5 (2.5s RTO)
    res = evaluate_resilience_rto_rpo(
        experiment_id="exp_res_01",
        target_service="payment-service",
        fault_injected_at=100.0,
        circuit_tripped_at=100.25,
        fault_removed_at=110.0,
        recovered_to_steady_at=112.5,
        total_fault_requests=100,
        fallback_success_requests=100,
        data_loss_window_seconds=0.0,
    )

    assert res.circuit_breaker_trip_time_ms == 250.0
    assert res.fallback_takeover_rate_pct == 100.0
    assert res.recovery_time_objective_seconds == 2.5
    assert res.recovery_point_objective_seconds == 0.0
    assert res.resilience_grade == ResilienceGrade.GRADE_A_RESILIENT
    assert res.is_slo_compliant is True
    assert any("卓越级韧性" in o for o in res.observations)


def test_evaluate_grade_b_acceptable():
    # 熔断触发 800ms, 恢复时间 8s, 降级接管率 92%
    res = evaluate_resilience_rto_rpo(
        experiment_id="exp_res_02",
        target_service="order-service",
        fault_injected_at=100.0,
        circuit_tripped_at=100.80,
        fault_removed_at=110.0,
        recovered_to_steady_at=118.0,
        total_fault_requests=100,
        fallback_success_requests=92,
        slo_max_rto_seconds=10.0,
    )

    assert res.circuit_breaker_trip_time_ms == 800.0
    assert res.fallback_takeover_rate_pct == 92.0
    assert res.recovery_time_objective_seconds == 8.0
    assert res.resilience_grade == ResilienceGrade.GRADE_B_ACCEPTABLE
    assert res.is_slo_compliant is True


def test_evaluate_grade_d_vulnerable_untripped():
    # 未能触发断路器熔断
    res = evaluate_resilience_rto_rpo(
        experiment_id="exp_res_03",
        target_service="stock-service",
        fault_injected_at=100.0,
        circuit_tripped_at=None,  # 未触发
        fault_removed_at=110.0,
        recovered_to_steady_at=None,
        total_fault_requests=100,
        fallback_success_requests=0,
    )

    assert res.circuit_breaker_trip_time_ms == 9999.0
    assert res.resilience_grade == ResilienceGrade.GRADE_D_VULNERABLE
    assert res.is_slo_compliant is False
    assert any("未能触发断路器熔断" in o for o in res.observations)

    d = res.to_dict()
    assert d["resilience_grade"] == "GRADE_D_VULNERABLE"
    assert d["is_slo_compliant"] is False
