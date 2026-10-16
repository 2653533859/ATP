"""Unit tests for C3.3 Sandbox Shadow Traffic Mirroring & Side-Effect Isolation Engine.

Tests:
1. TrafficMirrorPolicy route matching and outbound destination filtering
2. Intercepting prohibited write side-effects (payment, SMS, thirdparty)
3. Permitting safe read requests without interception
4. Batch mirrored traffic stream processing with zero-leakage safety verification
5. Isolation audit event recording and policy query
"""

from __future__ import annotations

import pytest

from app.services.sandbox_traffic_mirror import (
    _MIRROR_AUDIT_LOGS,
    _MIRROR_POLICIES,
    TrafficMirrorPolicy,
    get_policy_isolation_audit,
    intercept_outbound_side_effect,
    list_mirror_policies,
    process_mirrored_traffic_batch,
    register_mirror_policy,
)


@pytest.fixture(autouse=True)
def clean_mirror_state():
    _MIRROR_POLICIES.clear()
    _MIRROR_AUDIT_LOGS.clear()
    yield
    _MIRROR_POLICIES.clear()
    _MIRROR_AUDIT_LOGS.clear()


def test_mirror_policy_matching():
    policy = TrafficMirrorPolicy(
        policy_id="pol_orders_01",
        name="订单流量镜像策略",
        source_service="order-service",
        route_pattern=r"^/api/v1/orders.*",
        target_sandbox_id="sbx_test_881",
        enabled=True,
    )
    register_mirror_policy(policy)

    assert policy.matches_request("order-service", "/api/v1/orders/checkout") is True
    assert policy.matches_request("order-service", "/api/v1/users/profile") is False
    assert policy.matches_request("payment-service", "/api/v1/orders/checkout") is False

    policies = list_mirror_policies(only_enabled=True)
    assert len(policies) == 1


def test_intercept_prohibited_outbound_side_effects():
    policy = TrafficMirrorPolicy(
        policy_id="pol_pay_guard",
        name="支付与通知防穿透拦截策略",
        source_service="*",
        route_pattern=".*",
        target_sandbox_id="sbx_test_882",
        isolate_side_effects=True,
        blocked_outbound_patterns=["*payment*", "*charge*", "*sms*"],
    )
    register_mirror_policy(policy)

    # 1. Destructive POST payment -> must be intercepted
    intercepted, resp = intercept_outbound_side_effect(
        policy,
        destination="https://payment.gateway.internal/v1/charge",
        method="POST",
        payload={"amount": 99.0, "account": "acc_1001"},
    )
    assert intercepted is True
    assert resp["status_code"] == 200
    assert resp["body"]["isolated"] is True
    assert "拦截对" in resp["body"]["message"]

    # 2. Destructive POST SMS notification -> must be intercepted
    intercepted_sms, _ = intercept_outbound_side_effect(
        policy,
        destination="https://sms.provider.com/api/send",
        method="POST",
    )
    assert intercepted_sms is True

    # 3. Safe GET query -> not intercepted
    intercepted_get, _ = intercept_outbound_side_effect(
        policy,
        destination="https://payment.gateway.internal/v1/status",
        method="GET",
    )
    assert intercepted_get is False


def test_process_mirrored_traffic_batch_zero_leakage():
    policy = TrafficMirrorPolicy(
        policy_id="pol_batch_test",
        name="批处理镜像",
        source_service="order-service",
        route_pattern=r"^/orders.*",
        target_sandbox_id="sbx_batch_01",
        isolate_side_effects=True,
        blocked_outbound_patterns=["*charge*", "*payment*"],
    )
    register_mirror_policy(policy)

    traffic_batch = [
        {"service_name": "order-service", "path": "/orders/create"},
        {"service_name": "order-service", "path": "/orders/101"},
        {"service_name": "user-service", "path": "/users/me"},  # Unmatched
    ]

    outbound_calls = [
        {"destination": "https://bank.internal/api/charge", "method": "POST", "body": {"amount": 50}},
        {"destination": "https://cache.internal/get", "method": "GET"},
    ]

    res = process_mirrored_traffic_batch(
        policy_id="pol_batch_test",
        traffic_stream=traffic_batch,
        outbound_calls=outbound_calls,
    )

    assert res.total_candidate_requests == 3
    assert res.dispatched_to_sandbox_count == 2
    assert res.side_effects_intercepted_count == 1
    assert res.side_effects_leaked_count == 0
    assert res.isolation_safety_verified is True
    assert len(res.audit_events) == 1

    # Check audit log query
    audit = get_policy_isolation_audit("pol_batch_test")
    assert len(audit) == 1
    assert audit[0].target_destination == "https://bank.internal/api/charge"
