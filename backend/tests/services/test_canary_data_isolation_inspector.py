"""灰度流量数据隔离与影子存储防污染校验器单测 (T2.3)"""

from __future__ import annotations

from app.services.canary_data_isolation_inspector import (
    DataWriteAuditEvent,
    IsolationLeakSeverity,
    _is_critical_master_table,
    _is_legitimate_shadow_target,
    inspect_canary_data_isolation,
)


def test_target_table_patterns():
    assert _is_legitimate_shadow_target("t_order_shadow") is True
    assert _is_legitimate_shadow_target("t_payment_canary") is True
    assert _is_legitimate_shadow_target("sandbox_user_data") is True
    assert _is_legitimate_shadow_target("t_order") is False

    assert _is_critical_master_table("t_order") is True
    assert _is_critical_master_table("t_account_balance") is True
    assert _is_critical_master_table("t_inventory_stock") is True
    assert _is_critical_master_table("t_temp_cache") is False


def test_inspect_clean_isolated_canary_writes():
    events = [
        DataWriteAuditEvent(
            event_id="ev_01",
            target_service="order-service",
            is_canary_traffic=True,
            operation_type="INSERT",
            target_table_or_topic="t_order_shadow",
            statement_or_payload="INSERT INTO t_order_shadow ...",
            is_shadow_routed=True,
        ),
        DataWriteAuditEvent(
            event_id="ev_02",
            target_service="order-service",
            is_canary_traffic=True,
            operation_type="UPDATE",
            target_table_or_topic="t_order_item_canary",
            statement_or_payload="UPDATE t_order_item_canary ...",
            is_shadow_routed=False,  # 命名规则自动识别为影子表
        ),
    ]

    report = inspect_canary_data_isolation(events, target_service="order-service")
    assert report.total_write_events == 2
    assert report.shadow_routed_count == 2
    assert report.leaked_master_writes_count == 0
    assert report.isolation_compliance_pct == 100.0
    assert report.leak_severity == IsolationLeakSeverity.CLEAN_ISOLATED
    assert report.is_pollution_detected is False


def test_inspect_critical_leak_into_master_table():
    events = [
        DataWriteAuditEvent(
            event_id="ev_leak_01",
            target_service="payment-service",
            is_canary_traffic=True,  # 灰度染色流量
            operation_type="INSERT",
            target_table_or_topic="t_account_balance",  # 直接写入生产真实主表！
            statement_or_payload="UPDATE t_account_balance SET balance = balance - 100",
            is_shadow_routed=False,
        ),
        DataWriteAuditEvent(
            event_id="ev_clean_02",
            target_service="payment-service",
            is_canary_traffic=True,
            operation_type="INSERT",
            target_table_or_topic="t_payment_record_shadow",
            statement_or_payload="INSERT INTO t_payment_record_shadow ...",
            is_shadow_routed=True,
        ),
    ]

    report = inspect_canary_data_isolation(events, target_service="payment-service")
    assert report.total_write_events == 2
    assert report.leaked_master_writes_count == 1
    assert report.shadow_routed_count == 1
    assert report.isolation_compliance_pct == 50.0
    assert report.leak_severity == IsolationLeakSeverity.CRITICAL_LEAK
    assert report.is_pollution_detected is True
    assert len(report.leak_incidents) == 1
    assert report.leak_incidents[0].event_id == "ev_leak_01"

    d = report.to_dict()
    assert d["is_pollution_detected"] is True
    assert d["leak_severity"] == "CRITICAL_LEAK"


def test_inspect_baseline_traffic_not_flagged():
    # 正常基线流量写入生产主表是合法的，不应被判为泄漏
    events = [
        DataWriteAuditEvent(
            event_id="ev_base_01",
            target_service="order-service",
            is_canary_traffic=False,
            operation_type="INSERT",
            target_table_or_topic="t_order",
            statement_or_payload="INSERT INTO t_order ...",
            is_shadow_routed=False,
        )
    ]
    report = inspect_canary_data_isolation(events)
    assert report.leaked_master_writes_count == 0
    assert report.is_pollution_detected is False
    assert report.leak_severity == IsolationLeakSeverity.CLEAN_ISOLATED


def test_inspect_empty_events():
    report = inspect_canary_data_isolation([])
    assert report.total_write_events == 0
    assert report.isolation_compliance_pct == 100.0
    assert report.is_pollution_detected is False
