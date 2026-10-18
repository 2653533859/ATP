"""生产击穿毫秒级熔断与过载紧急泄压看门狗单测 (T2.2)"""

from __future__ import annotations

import pytest

from app.services.stress_safety_overload_guard import (
    OverloadGuardAction,
    ProductionHealthSnapshot,
    StressOverloadPolicy,
    evaluate_stress_overload_guard,
    execute_stress_circuit_break,
)
from app.services.stress_traffic_isolation_engine import (
    StressIsolationRule,
    StressTrafficRuleType,
    get_global_stress_manager,
)


@pytest.fixture(autouse=True)
def setup_stress_rules():
    mgr = get_global_stress_manager()
    mgr.clear()
    mgr._load_seed_rules()
    yield
    mgr.clear()
    mgr._load_seed_rules()


def test_evaluate_guard_normal_stress_safe():
    snap = ProductionHealthSnapshot(
        target_service="payment-service",
        measured_tps=3500.0,
        measured_error_rate_pct=0.05,
        measured_p99_latency_ms=85.0,
        measured_cpu_pct=52.0,
        measured_queue_depth=20,
    )

    verdict = evaluate_stress_overload_guard(snap)
    assert verdict.is_tripped is False
    assert verdict.action == OverloadGuardAction.NORMAL_STRESS_SAFE
    assert verdict.disabled_rules_count == 0
    assert "安全发压承载区" in verdict.verdict_message


def test_evaluate_guard_warning_load_high():
    # CPU 80% (高水位但未突破 85% 红线)
    snap = ProductionHealthSnapshot(
        target_service="payment-service",
        measured_tps=9500.0,
        measured_error_rate_pct=0.2,
        measured_p99_latency_ms=160.0,
        measured_cpu_pct=80.0,
        measured_queue_depth=80,
    )

    verdict = evaluate_stress_overload_guard(snap)
    assert verdict.is_tripped is False
    assert verdict.action == OverloadGuardAction.WARNING_LOAD_HIGH
    assert "保持施压观察" in verdict.verdict_message


def test_evaluate_guard_error_rate_breach_triggers_circuit_break():
    mgr = get_global_stress_manager()
    # 确保 payment-service 有启用的压测规则
    rule = StressIsolationRule(
        rule_id="r_st_pay",
        name="支付生产压测规则",
        rule_type=StressTrafficRuleType.URL_PATH_MATCH,
        target_service="payment-service",
        target_path_pattern="/pay/.*",
        is_enabled=True,
    )
    mgr.add_rule(rule)

    # 错误率突增至 2.4% (超过 1.0% 红线)
    snap = ProductionHealthSnapshot(
        target_service="payment-service",
        measured_tps=12000.0,
        measured_error_rate_pct=2.4,
        measured_p99_latency_ms=210.0,
        measured_cpu_pct=70.0,
    )

    verdict = evaluate_stress_overload_guard(snap)
    assert verdict.is_tripped is True
    assert verdict.action == OverloadGuardAction.TRIGGERED_CIRCUIT_BREAK
    assert any("错误率" in r for r in verdict.tripped_reasons)
    assert verdict.disabled_rules_count >= 1
    assert "紧急熔断" in verdict.verdict_message

    # 验证规则已被强制关闭切断
    updated = mgr.get_rule("r_st_pay")
    assert updated is not None
    assert updated.is_enabled is False


def test_evaluate_guard_cpu_breach():
    # CPU 达到 94% (突破 85% 红线)
    snap = ProductionHealthSnapshot(
        target_service="order-service",
        measured_tps=15000.0,
        measured_error_rate_pct=0.1,
        measured_p99_latency_ms=120.0,
        measured_cpu_pct=94.0,
    )

    verdict = evaluate_stress_overload_guard(snap)
    assert verdict.is_tripped is True
    assert verdict.action == OverloadGuardAction.TRIGGERED_CIRCUIT_BREAK
    assert any("CPU 使用率" in r for r in verdict.tripped_reasons)


def test_evaluate_guard_warning_when_auto_break_disabled():
    pol = StressOverloadPolicy(
        max_error_rate_pct=1.0,
        auto_circuit_break_enabled=False,  # 仅报警不断路
    )
    snap = ProductionHealthSnapshot(
        target_service="payment-service",
        measured_tps=16000.0,
        measured_error_rate_pct=3.0,
        measured_p99_latency_ms=450.0,
        measured_cpu_pct=90.0,
    )

    verdict = evaluate_stress_overload_guard(snap, policy=pol)
    assert verdict.is_tripped is True
    assert verdict.action == OverloadGuardAction.WARNING_LOAD_HIGH
    assert verdict.disabled_rules_count == 0
    assert "未开启自动断路" in verdict.verdict_message

    d = verdict.to_dict()
    assert d["is_tripped"] is True
    assert d["action"] == "WARNING_LOAD_HIGH"


def test_execute_stress_circuit_break_direct():
    cnt = execute_stress_circuit_break("payment-service", reason="人工干预急停")
    assert cnt >= 1
