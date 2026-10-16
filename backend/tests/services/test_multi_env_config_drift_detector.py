"""跨环境配置漂移自动探测与环境变量差分单元测试 (T2.1)。"""

from __future__ import annotations

import pytest
from app.services.multi_env_config_drift_detector import (
    DriftSeverity,
    DriftType,
    clear_config_drift_store,
    compare_environment_configs,
    get_config_drift_report,
    list_config_drift_reports,
    register_environment_config_snapshot,
)


@pytest.fixture(autouse=True)
def _reset_drift_state():
    clear_config_drift_store()
    yield
    clear_config_drift_store()


def test_compare_identical_configs():
    """测试当两环境配置完全相同时输出 100% 一致性与 IDENTICAL 状态。"""
    configs = {
        "APP_NAME": "order-service",
        "LOG_LEVEL": "INFO",
        "DATABASE_PORT": 5432,
    }
    report = compare_environment_configs(
        base_env="production",
        target_env="staging",
        service_name="order-service",
        base_configs=configs,
        target_configs=configs,
    )

    assert report.total_keys_checked == 3
    assert report.identical_count == 3
    assert report.drift_count == 0
    assert report.consistency_score_pct == 100.0
    assert report.highest_severity == DriftSeverity.IDENTICAL


def test_compare_missing_and_extra_and_mismatch():
    """测试探测缺失键 (MISSING)、冗余键 (EXTRA) 与取值漂移 (VALUE_MISMATCH)。"""
    base = {
        "DATABASE_URL": "postgresql://prod-db:5432/orders",
        "TIMEOUT_MS": 3000,
        "JWT_SECRET_KEY": "prod_super_secret_key_123",
        "BASE_FEATURE_FLAG": True,
    }
    target = {
        "DATABASE_URL": "postgresql://test-db:5432/orders",
        "TIMEOUT_MS": 30000,  # 差异悬殊
        # JWT_SECRET_KEY 缺失
        "DEBUG_LOCAL_PORT": 9999,  # 目标额外字段
    }

    report = compare_environment_configs(
        base_env="production",
        target_env="testing",
        service_name="order-service",
        base_configs=base,
        target_configs=target,
    )

    assert report.total_keys_checked == 5
    assert report.drift_count == 5  # 5 个键全有差异
    assert report.highest_severity == DriftSeverity.CRITICAL

    drifts_by_key = {d.key: d for d in report.drifts}

    # 1. JWT_SECRET_KEY 缺失 -> CRITICAL
    jwt_drift = drifts_by_key["JWT_SECRET_KEY"]
    assert jwt_drift.drift_type == DriftType.MISSING_IN_TARGET
    assert jwt_drift.severity == DriftSeverity.CRITICAL

    # 2. TIMEOUT_MS 取值漂移 -> HIGH
    timeout_drift = drifts_by_key["TIMEOUT_MS"]
    assert timeout_drift.drift_type == DriftType.VALUE_MISMATCH
    assert timeout_drift.severity == DriftSeverity.HIGH

    # 3. DEBUG_LOCAL_PORT 目标额外字段 -> LOW
    debug_drift = drifts_by_key["DEBUG_LOCAL_PORT"]
    assert debug_drift.drift_type == DriftType.EXTRA_IN_TARGET
    assert debug_drift.severity == DriftSeverity.LOW


def test_register_and_compare_from_snapshots():
    """测试通过配置快照仓库提取并比对。"""
    register_environment_config_snapshot(
        env_name="production",
        service_name="payment-service",
        configs={"PAYMENT_GATEWAY_URL": "https://api.alipay.com", "MAX_RETRY": 3},
    )
    register_environment_config_snapshot(
        env_name="testing",
        service_name="payment-service",
        configs={"PAYMENT_GATEWAY_URL": "https://sandbox.alipay.com", "MAX_RETRY": 3},
    )

    report = compare_environment_configs(
        base_env="production",
        target_env="testing",
        service_name="payment-service",
    )

    assert report.service_name == "payment-service"
    assert report.total_keys_checked == 2
    assert report.identical_count == 1
    assert report.drift_count == 1
    assert report.consistency_score_pct == 50.0

    # 验证报告已持久化
    saved_report = get_config_drift_report(report.report_id)
    assert saved_report is not None
    assert saved_report.report_id == report.report_id
    assert len(list_config_drift_reports()) == 1
