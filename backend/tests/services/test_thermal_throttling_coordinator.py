"""设备过热保护与温备降载协调器单测 (T2.2)"""

from __future__ import annotations

import pytest

from app.services.fleet_health_telemetry import (
    DeviceHealthStatus,
    clear_fleet_telemetry,
    get_device_telemetry,
    record_device_telemetry,
)
from app.services.thermal_throttling_coordinator import (
    ThermalActionTaken,
    ThermalPolicyTier,
    clear_thermal_coordinator_state,
    coordinate_device_thermal_policy,
    determine_thermal_tier,
    list_thermal_throttling_events,
    scan_and_coordinate_fleet_thermals,
)


@pytest.fixture(autouse=True)
def clean_state():
    clear_fleet_telemetry()
    clear_thermal_coordinator_state()
    yield
    clear_fleet_telemetry()
    clear_thermal_coordinator_state()


def test_determine_thermal_tier():
    assert determine_thermal_tier(34.0) == ThermalPolicyTier.NORMAL
    assert determine_thermal_tier(38.0) == ThermalPolicyTier.NORMAL
    assert determine_thermal_tier(39.5) == ThermalPolicyTier.THROTTLED
    assert determine_thermal_tier(42.0) == ThermalPolicyTier.THROTTLED
    assert determine_thermal_tier(43.5) == ThermalPolicyTier.EMERGENCY_COOLING


def test_thermal_lifecycle_throttling_and_restoration():
    # 1. 注册初始正常设备 (初始并发上限=4)
    record_device_telemetry(
        device_id="iphone_cool_01",
        platform="ios",
        battery_temp_c=32.0,
        battery_level=90,
        max_concurrency=4,
    )
    ev_init = coordinate_device_thermal_policy("iphone_cool_01")
    assert ev_init is None  # 处于正常温区无调整事件

    # 2. 升温至 40°C: 触发降载限流 (并发上限减半: 4 -> 2)
    record_device_telemetry(
        device_id="iphone_cool_01",
        platform="ios",
        battery_temp_c=40.0,
        battery_level=85,
        max_concurrency=4,
    )
    ev_throttle = coordinate_device_thermal_policy("iphone_cool_01")
    assert ev_throttle is not None
    assert ev_throttle.action_taken == ThermalActionTaken.CONCURRENCY_HALVED
    assert ev_throttle.adjusted_max_concurrency == 2
    dev = get_device_telemetry("iphone_cool_01")
    assert dev is not None
    assert dev.max_concurrency == 2
    assert dev.health_status == DeviceHealthStatus.WARMING

    # 3. 升温至 43.5°C: 触发紧急冷却 (并发归零，冻结调度)
    record_device_telemetry(
        device_id="iphone_cool_01",
        platform="ios",
        battery_temp_c=43.5,
        battery_level=80,
        max_concurrency=2,
    )
    ev_cooling = coordinate_device_thermal_policy("iphone_cool_01")
    assert ev_cooling is not None
    assert ev_cooling.action_taken == ThermalActionTaken.ENTER_EMERGENCY_COOLING
    assert ev_cooling.adjusted_max_concurrency == 0
    dev = get_device_telemetry("iphone_cool_01")
    assert dev is not None
    assert dev.health_status == DeviceHealthStatus.OVERHEATED
    # 4. 降温至 35°C: 恢复初始基线并发能力 (恢复至 4)
    record_device_telemetry(
        device_id="iphone_cool_01",
        platform="ios",
        battery_temp_c=35.0,
        battery_level=80,
        max_concurrency=0,
    )
    ev_restore = coordinate_device_thermal_policy("iphone_cool_01")
    assert ev_restore is not None
    assert ev_restore.action_taken == ThermalActionTaken.CAPACITY_RESTORED
    assert ev_restore.adjusted_max_concurrency == 4
    dev = get_device_telemetry("iphone_cool_01")
    assert dev is not None
    assert dev.max_concurrency == 4
    assert dev.health_status == DeviceHealthStatus.HEALTHY


def test_scan_fleet_thermals_and_history():
    record_device_telemetry("dev_scan_1", "ios", 40.5, 80, max_concurrency=2)
    record_device_telemetry("dev_scan_2", "android", 31.0, 90, max_concurrency=2)

    events = scan_and_coordinate_fleet_thermals()
    assert len(events) == 1
    assert events[0].device_id == "dev_scan_1"
    assert events[0].action_taken == ThermalActionTaken.CONCURRENCY_HALVED

    assert len(list_thermal_throttling_events()) == 1
