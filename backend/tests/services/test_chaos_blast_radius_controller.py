"""演练爆炸半径实时监控与紧急熔断回滚看门狗单测 (T2.2)"""

from __future__ import annotations

import pytest

from app.services.chaos_blast_radius_controller import (
    BlastRadiusObservation,
    BlastRadiusPolicy,
    BlastTripAction,
    check_blast_radius,
    is_tenant_exempt,
)
from app.services.chaos_fault_injector_library import get_global_fault_library
from app.services.chaos_steady_state_evaluator import get_global_chaos_manager


@pytest.fixture(autouse=True)
def setup_state():
    lib = get_global_fault_library()
    mgr = get_global_chaos_manager()
    yield
    lib.clear()
    lib._load_seed_faults()
    mgr.clear()
    mgr._load_seed_experiments()


def test_is_tenant_exempt():
    policy = BlastRadiusPolicy(
        policy_id="pol_1",
        experiment_id="exp_test",
        exempt_tenant_ids=["vip_001", "vip_002"],
    )
    assert is_tenant_exempt("vip_001", policy) is True
    assert is_tenant_exempt("normal_user", policy) is False
    assert is_tenant_exempt(None, policy) is False


def test_check_blast_radius_safe():
    policy = BlastRadiusPolicy(
        policy_id="pol_safe",
        experiment_id="exp_pay_circuit_breaker",
        max_impacted_services=2,
        max_error_rate_pct=5.0,
        latency_ceiling_ms=1000.0,
    )
    obs = BlastRadiusObservation(
        observation_id="obs_1",
        impacted_services=["payment-service"],
        current_error_rate_pct=1.5,
        current_p99_latency_ms=250.0,
    )

    verdict = check_blast_radius(policy, obs)
    assert verdict.is_tripped is False
    assert verdict.action == BlastTripAction.SAFE_CONTAINED
    assert len(verdict.tripped_rules) == 0
    assert len(verdict.teardown_actions_executed) == 0


def test_check_blast_radius_error_rate_breach_aborts():
    policy = BlastRadiusPolicy(
        policy_id="pol_abort",
        experiment_id="exp_pay_circuit_breaker",
        max_error_rate_pct=5.0,
        auto_abort_enabled=True,
    )
    # 错误率突增至 12% 击穿红线
    obs = BlastRadiusObservation(
        observation_id="obs_bad_rate",
        impacted_services=["payment-service"],
        current_error_rate_pct=12.0,
        current_p99_latency_ms=300.0,
    )

    verdict = check_blast_radius(policy, obs)
    assert verdict.is_tripped is True
    assert verdict.action == BlastTripAction.EMERGENCY_ABORT
    assert any("错误率击穿熔断红线" in r for r in verdict.tripped_rules)
    assert len(verdict.teardown_actions_executed) > 0


def test_check_blast_radius_service_count_exceeded():
    policy = BlastRadiusPolicy(
        policy_id="pol_srv",
        experiment_id="exp_pay_circuit_breaker",
        max_impacted_services=1,
        auto_abort_enabled=True,
    )
    # 波及了 3 个下游服务
    obs = BlastRadiusObservation(
        observation_id="obs_srv_spread",
        impacted_services=["payment-service", "order-service", "inventory-service"],
        current_error_rate_pct=2.0,
        current_p99_latency_ms=200.0,
    )

    verdict = check_blast_radius(policy, obs)
    assert verdict.is_tripped is True
    assert verdict.action == BlastTripAction.EMERGENCY_ABORT
    assert any("故障波及服务数超标" in r for r in verdict.tripped_rules)


def test_check_blast_radius_warning_when_auto_abort_disabled():
    policy = BlastRadiusPolicy(
        policy_id="pol_no_abort",
        experiment_id="exp_pay_circuit_breaker",
        max_error_rate_pct=5.0,
        auto_abort_enabled=False,  # 仅报警不自动熔断
    )
    obs = BlastRadiusObservation(
        observation_id="obs_warn",
        impacted_services=["payment-service"],
        current_error_rate_pct=8.0,
        current_p99_latency_ms=200.0,
    )

    verdict = check_blast_radius(policy, obs)
    assert verdict.is_tripped is True
    assert verdict.action == BlastTripAction.WARNING_BOUNDARY
    assert len(verdict.teardown_actions_executed) == 0

    d = verdict.to_dict()
    assert d["action"] == "WARNING_BOUNDARY"
    assert d["is_tripped"] is True
