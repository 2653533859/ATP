"""混沌演练非生产隔离与绝对安全围栏看门狗单测 (T4.1)"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from app.services.chaos_safety_boundary_guard import (
    SafetyVerdictAction,
    evaluate_chaos_safety_boundary,
    is_forbidden_target_asset,
    is_valid_safety_token,
)


def test_is_forbidden_target_asset():
    assert is_forbidden_target_asset("order-master-db", "/*") is True
    assert is_forbidden_target_asset("pg-cluster-writer", "/query") is True
    assert is_forbidden_target_asset("billing-settlement-core", "/settle") is True
    assert is_forbidden_target_asset("k8s-apiserver", "/api/v1") is True
    assert is_forbidden_target_asset("payment-service", "/api/v1/checkout") is False


def test_is_valid_safety_token():
    assert is_valid_safety_token("ATP-SAFETY-SECURE-20261017-XYZ99") is True
    assert is_valid_safety_token("INVALID-TOKEN") is False
    assert is_valid_safety_token("") is False
    assert is_valid_safety_token(None) is False


def test_evaluate_staging_safe_injection():
    verdict = evaluate_chaos_safety_boundary(
        environment="staging",
        target_service="order-service",
        target_pattern="/api/v1/orders/*",
        fault_type="NETWORK_LATENCY",
        config={"latency_ms": 500, "jitter_ms": 100},
    )
    assert verdict.is_allowed is True
    assert verdict.action == SafetyVerdictAction.ALLOW_SAFE
    assert len(verdict.block_reasons) == 0


def test_evaluate_forbidden_asset_blocked_even_in_staging():
    # 哪怕在测试环境，也严禁直接注入数据库主库
    verdict = evaluate_chaos_safety_boundary(
        environment="staging",
        target_service="mysql-primary-db",
        target_pattern="/*",
        fault_type="NETWORK_LATENCY",
        config={"latency_ms": 200},
    )
    assert verdict.is_allowed is False
    assert verdict.action == SafetyVerdictAction.BLOCKED_FORBIDDEN_ASSET
    assert any("绝对禁止注入高危资产黑名单" in r for r in verdict.block_reasons)


def test_evaluate_unsafe_operator_parameter_blocked():
    # 丢包率 90% 超过 80% 安全防线红线
    verdict = evaluate_chaos_safety_boundary(
        environment="test",
        target_service="payment-service",
        target_pattern="/api/v1/pay",
        fault_type="PACKET_LOSS",
        config={"packet_loss_rate": 0.9},
    )
    assert verdict.is_allowed is False
    assert verdict.action == SafetyVerdictAction.BLOCKED_UNSAFE_OPERATOR
    assert any("超过安全防线红线" in r for r in verdict.block_reasons)


def test_evaluate_production_unauthorized_blocked():
    now = datetime(2026, 10, 17, 14, 0, 0, tzinfo=timezone.utc)
    # 生产环境无工单、无维护窗口、无安全令牌
    verdict = evaluate_chaos_safety_boundary(
        environment="production",
        target_service="payment-service",
        target_pattern="/api/v1/pay",
        fault_type="NETWORK_LATENCY",
        config={"latency_ms": 400},
        current_time=now,
    )
    assert verdict.is_allowed is False
    assert verdict.action == SafetyVerdictAction.BLOCKED_PROD_UNAUTHORIZED
    assert len(verdict.block_reasons) >= 3


def test_evaluate_production_authorized_in_maintenance_window():
    now = datetime(2026, 10, 17, 3, 30, 0, tzinfo=timezone.utc)
    win_start = now - timedelta(hours=1)
    win_end = now + timedelta(hours=1)

    verdict = evaluate_chaos_safety_boundary(
        environment="prod",
        target_service="payment-service",
        target_pattern="/api/v1/pay",
        fault_type="NETWORK_LATENCY",
        config={"latency_ms": 300},
        approved_ticket_id="CHG-20261017-0091",
        maintenance_window_start=win_start,
        maintenance_window_end=win_end,
        safety_token="ATP-SAFETY-SECURE-20261017-ABC8899",
        current_time=now,
    )
    assert verdict.is_allowed is True
    assert verdict.action == SafetyVerdictAction.ALLOW_SAFE

    d = verdict.to_dict()
    assert d["is_allowed"] is True
    assert d["action"] == "ALLOW_SAFE"
