"""真机故障热转移与断点续跑自愈引擎单测 (T2.1)"""

from __future__ import annotations

import pytest

from app.services.device_hot_failover_engine import (
    FailoverStatus,
    FaultReason,
    HotFailoverResult,
    TaskExecutionContextSnapshot,
    clear_failover_history,
    execute_hot_failover,
    get_failover_result,
    list_failover_history,
)
from app.services.fleet_concurrency_router import clear_routing_state
from app.services.fleet_health_telemetry import (
    DeviceHealthStatus,
    clear_fleet_telemetry,
    get_device_telemetry,
    record_device_telemetry,
)


@pytest.fixture(autouse=True)
def clean_all():
    clear_fleet_telemetry()
    clear_routing_state()
    clear_failover_history()
    yield
    clear_fleet_telemetry()
    clear_routing_state()
    clear_failover_history()


def test_hot_failover_success_to_standby_device():
    # 注册出故障的原真机 (正在跑任务, 并发=1)
    record_device_telemetry("iphone_primary_01", "ios", 34.0, 80, current_concurrency=1, max_concurrency=2)
    # 注册温备真机 (空闲, 并发=0, 温度健康 30°C)
    record_device_telemetry("iphone_standby_02", "ios", 30.0, 95, current_concurrency=0, max_concurrency=2)

    snapshot = TaskExecutionContextSnapshot(
        task_id="task_checkout_e2e_888",
        platform="ios",
        failed_step_index=4,  # 在第 5 步发生故障 (前 4 步已成功)
        total_steps_count=8,
        completed_step_ids=["step_1", "step_2", "step_3", "step_4"],
        context_variables={"order_id": "OD_20261017_99", "user_token": "token_abc123"},
        original_device_id="iphone_primary_01",
    )

    result = execute_hot_failover(snapshot, FaultReason.TUNNEL_DISCONNECTED)
    assert isinstance(result, HotFailoverResult)
    assert result.status == FailoverStatus.MIGRATED_SUCCESS
    assert result.source_device_id == "iphone_primary_01"
    assert result.target_device_id == "iphone_standby_02"
    assert result.elapsed_ms < 500.0  # 满足 < 500ms 门禁

    # 查验原设备离线与并发扣减
    orig_dev = get_device_telemetry("iphone_primary_01")
    assert orig_dev is not None
    assert orig_dev.health_status == DeviceHealthStatus.OFFLINE
    assert orig_dev.current_concurrency == 0

    # 查验温备真机并发占用锁定 (+1)
    standby_dev = get_device_telemetry("iphone_standby_02")
    assert standby_dev is not None
    assert standby_dev.current_concurrency == 1

    # 查验断点续跑计划 (Resumption Plan)
    plan = result.resumption_plan
    assert plan is not None
    assert plan.target_device_id == "iphone_standby_02"
    assert plan.resume_from_step_index == 4
    assert plan.skip_steps_count == 4
    assert plan.remaining_steps_count == 4
    assert plan.restored_variables.get("order_id") == "OD_20261017_99"


def test_hot_failover_standby_exhausted():
    # 仅注册出故障的原真机，无任何同构备用机
    record_device_telemetry("android_primary_01", "android", 35.0, 70, current_concurrency=1, max_concurrency=2)

    snapshot = TaskExecutionContextSnapshot(
        task_id="task_and_fail_999",
        platform="android",
        failed_step_index=2,
        total_steps_count=5,
        completed_step_ids=["step_1", "step_2"],
        context_variables={},
        original_device_id="android_primary_01",
    )

    result = execute_hot_failover(snapshot, FaultReason.PROCESS_CRASH)
    assert result.status == FailoverStatus.STANDBY_EXHAUSTED
    assert result.target_device_id is None
    assert result.resumption_plan is None
    assert "温备真机已耗尽" in result.details


def test_failover_history_and_detail():
    record_device_telemetry("dev_a", "ios", 32.0, 80, current_concurrency=1, max_concurrency=2)
    record_device_telemetry("dev_b", "ios", 30.0, 90, current_concurrency=0, max_concurrency=2)

    snapshot = TaskExecutionContextSnapshot(
        task_id="task_hist_001",
        platform="ios",
        failed_step_index=1,
        total_steps_count=3,
        completed_step_ids=["s1"],
        context_variables={},
        original_device_id="dev_a",
    )

    res = execute_hot_failover(snapshot, FaultReason.HEARTBEAT_TIMEOUT)
    assert get_failover_result(res.failover_id) is not None
    assert len(list_failover_history()) == 1

    d = res.to_dict()
    assert d["failover_id"].startswith("failover_")
    assert d["fault_reason"] == "HEARTBEAT_TIMEOUT"
    assert d["status"] == "MIGRATED_SUCCESS"
