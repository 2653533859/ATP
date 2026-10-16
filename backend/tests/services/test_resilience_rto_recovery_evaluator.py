"""Unit tests for Resilience RTO Recovery Evaluator Service (T4.2)."""

from __future__ import annotations

import pytest

from app.services.resilience_rto_recovery_evaluator import (
    ResilienceTier,
    analyze_resilience_rto,
    clear_rto_reports,
    get_rto_report,
    list_rto_reports,
    simulate_circuit_breaker_exercise,
)


@pytest.fixture(autouse=True)
def clean_reports():
    clear_rto_reports()
    yield
    clear_rto_reports()


def test_analyze_empty_samples():
    """验证空时序采样点时的保底降级逻辑。"""
    rep = analyze_resilience_rto("order-service", "POST /checkout", [])
    assert rep.total_samples_analyzed == 0
    assert rep.resilience_tier == ResilienceTier.FRAGILE
    assert "无法评定" in rep.verdict_summary


def test_analyze_excellent_resilience():
    """验证快速熔断跳闸、100% 降级且极速自愈的 EXCELLENT 判定。"""
    samples = [
        # 1. 正常期 (0, 50ms)
        {
            "seq": 1,
            "offset_ms": 0.0,
            "status_code": 200,
            "is_fault_active": False,
            "is_fallback": False,
            "breaker_state": "CLOSED",
        },
        {
            "seq": 2,
            "offset_ms": 50.0,
            "status_code": 200,
            "is_fault_active": False,
            "is_fallback": False,
            "breaker_state": "CLOSED",
        },
        # 2. 故障期 (100~300ms)，并在 150ms 处断路器立即跳闸 OPEN
        {
            "seq": 3,
            "offset_ms": 100.0,
            "status_code": 503,
            "is_fault_active": True,
            "is_fallback": False,
            "breaker_state": "CLOSED",
        },
        {
            "seq": 4,
            "offset_ms": 150.0,
            "status_code": 200,
            "is_fault_active": True,
            "is_fallback": True,
            "breaker_state": "OPEN",
        },
        {
            "seq": 5,
            "offset_ms": 200.0,
            "status_code": 200,
            "is_fault_active": True,
            "is_fallback": True,
            "breaker_state": "OPEN",
        },
        {
            "seq": 6,
            "offset_ms": 300.0,
            "status_code": 200,
            "is_fault_active": True,
            "is_fallback": True,
            "breaker_state": "OPEN",
        },
        # 3. 故障消除期 (350~500ms)，并在 450ms 处恢复 CLOSED
        {
            "seq": 7,
            "offset_ms": 350.0,
            "status_code": 200,
            "is_fault_active": False,
            "is_fallback": True,
            "breaker_state": "HALF_OPEN",
        },
        {
            "seq": 8,
            "offset_ms": 450.0,
            "status_code": 200,
            "is_fault_active": False,
            "is_fallback": False,
            "breaker_state": "CLOSED",
        },
    ]

    report = analyze_resilience_rto(
        target_service_id="payment-service",
        endpoint="POST /pay",
        sample_points=samples,
    )

    # 跳闸时延: 150ms - 100ms = 50ms (<= 150ms)
    assert report.breaker_trip_latency_ms == 50.0
    # 故障期间4个请求，3个成功降级 -> 75%
    # 自愈时长: 450ms - 300ms = 150ms (<= 800ms)
    assert report.rto_recovery_duration_ms == 150.0


def test_analyze_fragile_no_circuit_breaker_tripped():
    """验证断路器在故障期间从未跳闸的 FRAGILE 严重缺陷评定。"""
    samples = [
        {
            "seq": 1,
            "offset_ms": 0.0,
            "status_code": 200,
            "is_fault_active": False,
            "is_fallback": False,
            "breaker_state": "CLOSED",
        },
        # 故障期间全程 503 且断路器一直处于 CLOSED，未跳闸
        {
            "seq": 2,
            "offset_ms": 100.0,
            "status_code": 503,
            "is_fault_active": True,
            "is_fallback": False,
            "breaker_state": "CLOSED",
        },
        {
            "seq": 3,
            "offset_ms": 200.0,
            "status_code": 503,
            "is_fault_active": True,
            "is_fallback": False,
            "breaker_state": "CLOSED",
        },
        {
            "seq": 4,
            "offset_ms": 300.0,
            "status_code": 503,
            "is_fault_active": True,
            "is_fallback": False,
            "breaker_state": "CLOSED",
        },
        # 故障结束后依然未自愈
        {
            "seq": 5,
            "offset_ms": 400.0,
            "status_code": 500,
            "is_fault_active": False,
            "is_fallback": False,
            "breaker_state": "CLOSED",
        },
    ]

    report = analyze_resilience_rto(
        target_service_id="order-service",
        endpoint="POST /checkout",
        sample_points=samples,
    )

    assert report.resilience_tier == ResilienceTier.FRAGILE
    assert report.breaker_trip_latency_ms == 9999.0
    assert report.fallback_success_ratio_pct == 0.0
    assert report.rto_recovery_duration_ms == 9999.0
    assert len(report.remediation_suggestions) > 0


def test_simulate_circuit_breaker_exercise_presets():
    """验证仿真模拟运行器生成各等级预设报告。"""
    # 1. 卓越预设
    rep_exc = simulate_circuit_breaker_exercise(
        target_service_id="order-service",
        endpoint="POST /api/v1/orders/checkout",
        tier_preset="EXCELLENT",
    )
    assert rep_exc.total_samples_analyzed == 28
    assert rep_exc.resilience_tier in (ResilienceTier.EXCELLENT, ResilienceTier.ADEQUATE)
    assert rep_exc.breaker_trip_latency_ms <= 100.0
    assert rep_exc.rto_recovery_duration_ms <= 800.0

    # 2. 脆弱预设
    rep_frag = simulate_circuit_breaker_exercise(
        target_service_id="order-service",
        endpoint="POST /api/v1/orders/checkout",
        tier_preset="FRAGILE",
    )
    assert rep_frag.resilience_tier in (ResilienceTier.FRAGILE, ResilienceTier.INSUFFICIENT)

    # 3. 报告持久化验证
    fetched = get_rto_report(rep_exc.report_id)
    assert fetched is not None
    assert fetched.report_id == rep_exc.report_id
    assert len(list_rto_reports()) == 2
