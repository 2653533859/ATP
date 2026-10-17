"""物理真机动态多目标加权并发路由引擎单测 (T1.2)"""

from __future__ import annotations

import pytest

from app.services.fleet_concurrency_router import (
    RoutingStatus,
    TaskExecutionRequirement,
    TaskPriority,
    clear_routing_state,
    get_routing_decision,
    list_routing_history,
    release_device_lease,
    route_and_lease_device,
)
from app.services.fleet_health_telemetry import (
    clear_fleet_telemetry,
    get_device_telemetry,
    record_device_telemetry,
)


@pytest.fixture(autouse=True)
def clean_all():
    clear_fleet_telemetry()
    clear_routing_state()
    yield
    clear_fleet_telemetry()
    clear_routing_state()


def test_route_and_lease_selects_best_healthy_device():
    # 注册两台同构 iOS 真机:
    # 设备 A: 温度较低 (30°C), 电量高 (90%), 并发空闲 (0/2)
    record_device_telemetry("iphone_A", "ios", 30.0, 90, current_concurrency=0, max_concurrency=2)
    # 设备 B: 温度较高 (38°C), 电量较低 (50%), 当前已有 1 个并发 (1/2)
    record_device_telemetry("iphone_B", "ios", 38.0, 50, current_concurrency=1, max_concurrency=2)

    req = TaskExecutionRequirement(
        task_id="task_ios_checkout_01",
        target_platform="ios",
        task_name="iOS 收银台支付测试",
        priority=TaskPriority.HIGH,
    )

    res = route_and_lease_device(req)
    assert res.status == RoutingStatus.ROUTED
    assert res.selected_device_id == "iphone_A"
    assert res.fitness_score >= 90.0

    # 查验证实并发租约锁定 (+1)
    dev_a = get_device_telemetry("iphone_A")
    assert dev_a is not None
    assert dev_a.current_concurrency == 1

    # 释放租约
    ok = release_device_lease("iphone_A", "task_ios_checkout_01")
    assert ok is True
    assert dev_a.current_concurrency == 0


def test_route_queued_when_all_devices_disqualified():
    # 注册一台过热的 Android 设备
    record_device_telemetry("android_hot", "android", 43.5, 80, current_concurrency=0, max_concurrency=2)

    req = TaskExecutionRequirement(
        task_id="task_and_02",
        target_platform="android",
        max_temperature_c=40.0,
    )

    res = route_and_lease_device(req)
    assert res.status == RoutingStatus.QUEUED
    assert res.selected_device_id is None
    assert "未通过准入门禁" in res.routing_reason


def test_route_no_available_device_when_no_device_registered():
    req = TaskExecutionRequirement(
        task_id="task_empty_03",
        target_platform="ios",
    )
    res = route_and_lease_device(req)
    assert res.status == RoutingStatus.NO_AVAILABLE_DEVICE
    assert res.selected_device_id is None


def test_routing_history_and_detail():
    record_device_telemetry("dev_test_hist", "ios", 32.0, 80, current_concurrency=0, max_concurrency=2)
    req = TaskExecutionRequirement("task_h1", "ios")

    res = route_and_lease_device(req)
    assert get_routing_decision(res.decision_id) is not None
    assert len(list_routing_history()) == 1

    d = res.to_dict()
    assert d["decision_id"].startswith("route_")
    assert d["selected_device_id"] == "dev_test_hist"
    assert len(d["candidate_evaluations"]) == 1
