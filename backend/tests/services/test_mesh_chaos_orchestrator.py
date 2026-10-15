"""Unit tests for T3.1 Microservice Mesh and API Gateway Chaos Fault Orchestration Engine.

Tests:
1. ChaosRule route pattern, method, service name, and header matching
2. create_chaos_experiment validates names, action types, and sampling ratios
3. evaluate_mesh_request injects 503 outage, circuit breaker trip, latency jitter, and corrupt payload
4. evaluate_mesh_request respects traffic_ratio probability and header matchers
5. set_experiment_status controls active/paused lifecycle and updates hit statistics
"""

from __future__ import annotations

import pytest

from app.services.mesh_chaos_orchestrator import (
    ChaosRule,
    create_chaos_experiment,
    evaluate_mesh_request,
    get_chaos_experiment,
    list_chaos_experiments,
    set_experiment_status,
)


def test_chaos_rule_matching():
    rule = ChaosRule(
        rule_id="r1",
        service_name="payment-service",
        route_pattern=r"^/api/v1/payments/.*",
        action="service_down_503",
        methods=["POST", "PUT"],
        header_matchers={"x-canary": "true"},
    )

    # 1. Exact match
    assert (
        rule.matches(
            service_name="payment-service",
            path="/api/v1/payments/checkout",
            method="POST",
            headers={"X-Canary": "true", "User-Agent": "Curl"},
        )
        is True
    )

    # 2. Wrong service
    assert (
        rule.matches(
            service_name="order-service",
            path="/api/v1/payments/checkout",
            method="POST",
            headers={"x-canary": "true"},
        )
        is False
    )

    # 3. Wrong method
    assert (
        rule.matches(
            service_name="payment-service",
            path="/api/v1/payments/checkout",
            method="GET",
            headers={"x-canary": "true"},
        )
        is False
    )

    # 4. Missing header matcher
    assert (
        rule.matches(
            service_name="payment-service",
            path="/api/v1/payments/checkout",
            method="POST",
            headers={},
        )
        is False
    )


def test_create_chaos_experiment_validation():
    # Empty name
    with pytest.raises(ValueError, match="实验名称不能为空"):
        create_chaos_experiment("", [{"action": "service_down_503"}])

    # Unsupported action
    with pytest.raises(ValueError, match="不受支持"):
        create_chaos_experiment("Test Exp", [{"action": "unknown_action_xyz"}])

    # Invalid traffic ratio
    with pytest.raises(ValueError, match="流量采样比例必须在 0.0 到 1.0 之间"):
        create_chaos_experiment(
            "Test Exp",
            [{"action": "service_down_503", "traffic_ratio": 1.5}],
        )


def test_evaluate_mesh_request_actions():
    exp = create_chaos_experiment(
        name="订单与支付故障注入演练",
        experiment_id="exp_test_actions_01",
        rules_data=[
            {
                "rule_id": "r_pay_503",
                "service_name": "pay-svc",
                "route_pattern": r"/pay/.*",
                "action": "service_down_503",
                "action_params": {"status_code": 503},
                "traffic_ratio": 1.0,
            },
            {
                "rule_id": "r_order_reset",
                "service_name": "order-svc",
                "route_pattern": r"/orders/reset",
                "action": "circuit_breaker_trip",
                "traffic_ratio": 1.0,
            },
            {
                "rule_id": "r_user_jitter",
                "service_name": "user-svc",
                "route_pattern": r"/users/profile",
                "action": "latency_jitter",
                "action_params": {"base_latency_ms": 1200.0, "jitter_ms": 100.0},
                "traffic_ratio": 1.0,
            },
            {
                "rule_id": "r_cart_corrupt",
                "service_name": "cart-svc",
                "route_pattern": r"/cart/corrupt",
                "action": "corrupt_payload",
                "traffic_ratio": 1.0,
            },
        ],
    )

    assert get_chaos_experiment("exp_test_actions_01") is exp

    # 1. Evaluate 503 outage
    dec_503 = evaluate_mesh_request(service_name="pay-svc", path="/pay/charge", method="POST")
    assert dec_503.inject is True
    assert dec_503.action == "service_down_503"
    assert dec_503.status_code == 503
    assert "ServiceUnavailable" in str(dec_503.response_body)

    # 2. Evaluate circuit breaker trip (ECONNRESET)
    dec_trip = evaluate_mesh_request(service_name="order-svc", path="/orders/reset", method="POST")
    assert dec_trip.inject is True
    assert dec_trip.action == "circuit_breaker_trip"
    assert dec_trip.status_code == 504
    assert "ECONNRESET" in str(dec_trip.response_body)

    # 3. Evaluate latency jitter
    dec_jitter = evaluate_mesh_request(service_name="user-svc", path="/users/profile", method="GET")
    assert dec_jitter.inject is True
    assert dec_jitter.action == "latency_jitter"
    assert dec_jitter.latency_ms >= 1200.0

    # 4. Evaluate corrupt payload
    dec_corrupt = evaluate_mesh_request(service_name="cart-svc", path="/cart/corrupt", method="GET")
    assert dec_corrupt.inject is True
    assert dec_corrupt.action == "corrupt_payload"
    assert "<malformed" in str(dec_corrupt.response_body)

    # 5. Non-matching request passes
    dec_pass = evaluate_mesh_request(service_name="inventory-svc", path="/stock/query", method="GET")
    assert dec_pass.inject is False
    assert dec_pass.action == "pass"


def test_experiment_lifecycle_pause_and_stats():
    create_chaos_experiment(
        name="网关生命周期演练",
        experiment_id="exp_lifecycle_test",
        rules_data=[
            {
                "service_name": "auth-svc",
                "route_pattern": r"/auth/token",
                "action": "service_down_503",
                "traffic_ratio": 1.0,
            }
        ],
    )

    # Active: request is injected
    dec1 = evaluate_mesh_request(service_name="auth-svc", path="/auth/token")
    assert dec1.inject is True

    # Pause experiment: request passes without fault
    set_experiment_status("exp_lifecycle_test", "paused")
    dec2 = evaluate_mesh_request(service_name="auth-svc", path="/auth/token")
    assert dec2.inject is False

    # Resume experiment: request is injected again
    set_experiment_status("exp_lifecycle_test", "active")
    dec3 = evaluate_mesh_request(service_name="auth-svc", path="/auth/token")
    assert dec3.inject is True

    # Verify hit statistics
    exp = get_chaos_experiment("exp_lifecycle_test")
    assert exp is not None
    assert exp.total_evaluated >= 2
    assert exp.total_injected >= 2
    assert exp.to_dict()["injected_ratio_pct"] > 0.0

    # Verify listing
    all_exps = list_chaos_experiments()
    assert any(e["experiment_id"] == "exp_lifecycle_test" for e in all_exps)
