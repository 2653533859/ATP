"""Unit Tests for Sagas/TCC Distributed Transaction State Tracker (T2.1)。"""

from __future__ import annotations

import pytest

from app.services.saga_transaction_state_tracker import (
    GlobalTxStatus,
    SagaAnomalyType,
    audit_global_tx,
    clear_saga_store,
    list_active_and_hanging_transactions,
    record_branch_tx,
    record_global_tx,
    simulate_saga_scenario,
)


@pytest.fixture(autouse=True)
def clean_store():
    clear_saga_store()
    yield
    clear_saga_store()


def test_normal_tcc_transaction_commit():
    gid = "gtx_normal_101"
    record_global_tx(global_tx_id=gid, business_key="order_1001", pattern="TCC")

    # order-service: Try -> Confirm
    record_branch_tx(gid, "order-service", "create_order", stage="TRY", status="SUCCESS")
    record_branch_tx(gid, "order-service", "create_order", stage="CONFIRM", status="SUCCESS")

    # pay-service: Try -> Confirm
    record_branch_tx(gid, "pay-service", "deduct_balance", stage="TRY", status="SUCCESS")
    record_branch_tx(gid, "pay-service", "deduct_balance", stage="CONFIRM", status="SUCCESS")

    audit = audit_global_tx(gid)
    assert audit is not None
    assert audit.is_consistent is True
    assert audit.status == GlobalTxStatus.COMMITTED
    assert audit.detected_anomaly == SagaAnomalyType.NONE
    assert "最终一致性达标" in audit.anomaly_description


def test_hanging_transaction_detection():
    # 模拟网络乱序导致的悬挂：Cancel 优先到达并执行，晚到的 Try 导致资源冻结但永无后续 Confirm/Cancel
    gid = "gtx_hanging_202"
    record_global_tx(global_tx_id=gid, business_key="order_1002", pattern="TCC")

    # order-service 正常 Try
    record_branch_tx(gid, "order-service", "create_order", stage="TRY", status="SUCCESS")

    # pay-service 由于网络抖动，直接收到了协调器的 CANCEL 并成功执行
    record_branch_tx(gid, "pay-service", "deduct_balance", stage="CANCEL", status="SUCCESS")

    # 稍后，因网络重发迟滞的 TRY 终于到达 pay-service
    record_branch_tx(gid, "pay-service", "deduct_balance", stage="TRY", status="SUCCESS")

    audit = audit_global_tx(gid)
    assert audit is not None
    assert audit.is_consistent is False
    assert audit.status == GlobalTxStatus.HANGING
    assert audit.detected_anomaly == SagaAnomalyType.HANGING_TRANSACTION
    assert "悬挂事务" in audit.anomaly_description
    assert len(audit.remediation_advice) > 0
    assert "防悬挂" in audit.remediation_advice[1]


def test_empty_compensation_detection():
    # 模拟空补偿：业务从未执行过 Try，但由于整体回滚，直接收到 Cancel
    gid = "gtx_empty_comp_303"
    record_global_tx(global_tx_id=gid, business_key="order_1003", pattern="TCC")

    # 仅收到 inventory 的 Cancel，无 Try
    record_branch_tx(gid, "inventory-service", "lock_stock", stage="CANCEL", status="SUCCESS")

    audit = audit_global_tx(gid)
    assert audit is not None
    assert audit.is_consistent is False
    assert audit.detected_anomaly == SagaAnomalyType.EMPTY_COMPENSATION
    assert "空补偿" in audit.anomaly_description


def test_partial_commit_inconsistency_detection():
    # 模拟部分提交失败导致数据撕裂
    gid = "gtx_partial_fail_404"
    record_global_tx(global_tx_id=gid, business_key="order_1004", pattern="TCC")

    # 分支 1 确认提交成功
    record_branch_tx(gid, "order-service", "create_order", stage="CONFIRM", status="SUCCESS")
    # 分支 2 失败且尚未补偿
    record_branch_tx(gid, "pay-service", "deduct_balance", stage="TRY", status="FAILED", error_message="bank error")

    audit = audit_global_tx(gid)
    assert audit is not None
    assert audit.is_consistent is False
    assert audit.status == GlobalTxStatus.INCONSISTENT
    assert audit.detected_anomaly == SagaAnomalyType.PARTIAL_COMMIT_FAILURE
    assert "跨服务数据最终一致性撕裂" in audit.anomaly_description


def test_rollback_consistency():
    gid = "gtx_rollback_505"
    record_global_tx(global_tx_id=gid, business_key="order_1005", pattern="TCC")

    # 发生了失败并成功补偿
    record_branch_tx(gid, "order-service", "create_order", stage="TRY", status="SUCCESS")
    record_branch_tx(gid, "pay-service", "deduct_balance", stage="TRY", status="FAILED")
    record_branch_tx(gid, "order-service", "create_order", stage="CANCEL", status="SUCCESS")

    audit = audit_global_tx(gid)
    assert audit is not None
    assert audit.is_consistent is True
    assert audit.status == GlobalTxStatus.ROLLED_BACK


def test_simulate_saga_scenarios_and_list_hanging():
    # 仿真四种场景
    sim_hanging = simulate_saga_scenario("hanging")
    assert sim_hanging.detected_anomaly == SagaAnomalyType.HANGING_TRANSACTION

    sim_empty = simulate_saga_scenario("empty_compensation")
    assert sim_empty.detected_anomaly == SagaAnomalyType.EMPTY_COMPENSATION

    sim_normal = simulate_saga_scenario("normal")
    assert sim_normal.is_consistent is True

    hanging_list = list_active_and_hanging_transactions()
    assert len(hanging_list) >= 2
