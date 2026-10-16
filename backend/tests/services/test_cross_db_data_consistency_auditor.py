"""Unit Tests for Cross-Database Eventual Consistency Auditor (T2.2)。"""

from __future__ import annotations

import pytest

from app.services.cross_db_data_consistency_auditor import (
    AuditVerdictStatus,
    MismatchCategory,
    clear_audit_store,
    delete_audit_rule,
    execute_consistency_audit,
    get_audit_report,
    list_audit_rules,
    register_audit_rule,
)


@pytest.fixture(autouse=True)
def clean_store():
    clear_audit_store()
    yield
    clear_audit_store()


def test_reconciled_100_percent_scenario():
    rule = register_audit_rule(
        rule_name="订单-支付对账",
        source_service="order-service",
        source_table="orders",
        target_service="pay-service",
        target_table="payments",
        join_key="order_id",
        field_mappings={"amount": "paid_amount", "status": "payment_status"},
        numeric_tolerance=0.01,
        tolerance_threshold_pct=98.0,
    )

    source_records = [
        {"order_id": "ord_1", "amount": 100.0, "status": "PAID"},
        {"order_id": "ord_2", "amount": 250.50, "status": "REFUNDED"},
    ]
    target_records = [
        {"order_id": "ord_1", "paid_amount": 100.0, "payment_status": "PAID"},
        {"order_id": "ord_2", "paid_amount": 250.50, "payment_status": "REFUNDED"},
    ]

    report = execute_consistency_audit(rule, source_records, target_records)

    assert report.verdict == AuditVerdictStatus.RECONCILED
    assert report.consistency_rate_pct == 100.0
    assert report.total_records_checked == 2
    assert report.consistent_records_count == 2
    assert report.mismatched_records_count == 0
    assert len(report.diff_records) == 0


def test_missing_in_target_and_remediation_sql():
    rule = register_audit_rule(
        rule_name="订单同步对账",
        source_service="order-service",
        source_table="orders",
        target_service="analytics-service",
        target_table="order_dw",
        join_key="order_id",
        tolerance_threshold_pct=90.0,
    )

    source_records = [
        {"order_id": "ord_1", "user_id": 101, "total": 99.0},
        {"order_id": "ord_2", "user_id": 102, "total": 199.0},  # 目标库缺失
    ]
    target_records = [
        {"order_id": "ord_1", "user_id": 101, "total": 99.0},
    ]

    report = execute_consistency_audit(rule, source_records, target_records)

    assert report.total_records_checked == 2
    assert report.missing_in_target_count == 1
    assert report.consistent_records_count == 1
    assert report.mismatched_records_count == 1

    diff = report.diff_records[0]
    assert diff.join_key_value == "ord_2"
    assert diff.category == MismatchCategory.MISSING_IN_TARGET
    assert "INSERT INTO order_dw" in diff.remediation_sql


def test_missing_in_source_ghost_data():
    rule = register_audit_rule(
        rule_name="幽灵数据检查",
        source_service="order-service",
        source_table="orders",
        target_service="inventory-service",
        target_table="stock_deductions",
        join_key="order_id",
    )

    source_records = [
        {"order_id": "ord_1"},
    ]
    target_records = [
        {"order_id": "ord_1"},
        {"order_id": "ord_ghost"},  # 上游源缺失
    ]

    report = execute_consistency_audit(rule, source_records, target_records)
    assert report.missing_in_source_count == 1
    diff = next(d for d in report.diff_records if d.join_key_value == "ord_ghost")
    assert diff.category == MismatchCategory.MISSING_IN_SOURCE
    assert "DELETE FROM stock_deductions" in diff.remediation_sql


def test_field_value_mismatch_with_numeric_tolerance():
    rule = register_audit_rule(
        rule_name="数值容差与状态比对",
        source_service="order-service",
        source_table="orders",
        target_service="pay-service",
        target_table="payments",
        join_key="order_id",
        field_mappings={"amount": "amount", "status": "status"},
        numeric_tolerance=0.005,  # 0.005 容差
        tolerance_threshold_pct=50.0,
    )

    source_records = [
        # 微小浮点误差: 100.002 vs 100.000 (差距 0.002 <= 0.005 -> 视为一致)
        {"order_id": "ord_tol", "amount": 100.002, "status": "SUCCESS"},
        # 实际不一致: amount 差 10.0，且 status 冲突
        {"order_id": "ord_mismatch", "amount": 200.0, "status": "PAID"},
    ]
    target_records = [
        {"order_id": "ord_tol", "amount": 100.000, "status": "SUCCESS"},
        {"order_id": "ord_mismatch", "amount": 190.0, "status": "PENDING"},
    ]

    report = execute_consistency_audit(rule, source_records, target_records)

    assert report.total_records_checked == 2
    assert report.consistent_records_count == 1
    assert report.value_mismatches_count == 1

    diff = report.diff_records[0]
    assert diff.join_key_value == "ord_mismatch"
    assert diff.category == MismatchCategory.FIELD_VALUE_MISMATCH
    assert len(diff.field_diffs) == 2  # amount + status
    assert "UPDATE payments SET" in diff.remediation_sql


def test_audit_rules_crud_and_report_retrieval():
    rule = register_audit_rule(
        rule_name="CRUD测试规则",
        source_service="s1",
        source_table="t1",
        target_service="s2",
        target_table="t2",
        join_key="id",
        rule_id="r_crud_1",
    )
    assert len(list_audit_rules()) == 1

    report = execute_consistency_audit(rule, [{"id": "1"}], [{"id": "1"}])
    assert get_audit_report(report.report_id) is not None

    assert delete_audit_rule("r_crud_1") is True
    assert len(list_audit_rules()) == 0
