"""物理真机集群健康多维遥测与感知器单测 (T1.1)"""

from __future__ import annotations

import pytest

from app.services.fleet_health_telemetry import (
    BatteryState,
    DeviceHealthMetric,
    DeviceHealthStatus,
    calculate_health_score,
    clear_fleet_telemetry,
    get_device_telemetry,
    is_device_eligible_for_dispatch,
    list_fleet_telemetry,
    record_device_telemetry,
)


@pytest.fixture(autouse=True)
def clean_store():
    clear_fleet_telemetry()
    yield
    clear_fleet_telemetry()


def test_calculate_health_score_optimal_and_overheated():
    # 1. 最优状态
    optimal = DeviceHealthMetric(
        device_id="iphone_opt_01",
        platform="ios",
        battery_temperature_c=31.5,
        battery_level_percent=90,
        tunnel_rtt_ms=10.0,
        current_concurrency=0,
        max_concurrency=2,
    )
    score, status = calculate_health_score(optimal)
    assert score == 100.0
    assert status == DeviceHealthStatus.HEALTHY

    # 2. 超温过热状态 (>42°C)
    overheated = DeviceHealthMetric(
        device_id="iphone_hot_02",
        platform="ios",
        battery_temperature_c=43.5,
        battery_level_percent=70,
        tunnel_rtt_ms=20.0,
        current_concurrency=1,
        max_concurrency=2,
    )
    score_hot, status_hot = calculate_health_score(overheated)
    assert status_hot == DeviceHealthStatus.OVERHEATED
    assert score_hot < 65.0


def test_calculate_health_score_low_battery():
    low_bat = DeviceHealthMetric(
        device_id="android_low_03",
        platform="android",
        battery_temperature_c=33.0,
        battery_level_percent=15,  # <20%
        tunnel_rtt_ms=15.0,
        current_concurrency=0,
        max_concurrency=2,
    )
    _, status = calculate_health_score(low_bat)
    assert status == DeviceHealthStatus.LOW_BATTERY


def test_record_and_list_telemetry():
    m1 = record_device_telemetry(
        device_id="dev_01",
        platform="ios",
        battery_temp_c=32.0,
        battery_level=85,
        battery_state=BatteryState.CHARGING,
    )
    assert m1.health_score >= 95.0
    assert m1.health_status == DeviceHealthStatus.HEALTHY

    m2 = record_device_telemetry(
        device_id="dev_02",
        platform="android",
        battery_temp_c=43.0,
        battery_level=60,
    )
    assert m2.health_status == DeviceHealthStatus.OVERHEATED

    # 查询单台与全量
    assert get_device_telemetry("dev_01") is not None
    assert len(list_fleet_telemetry()) == 2
    assert len(list_fleet_telemetry(platform="ios")) == 1

    # 序列化验证
    d = m1.to_dict()
    assert d["device_id"] == "dev_01"
    assert d["health_status"] == "HEALTHY"
    assert d["battery_state"] == "CHARGING"


def test_is_device_eligible_for_dispatch():
    # 1. 未录入心跳
    ok1, reason1 = is_device_eligible_for_dispatch("dev_unknown")
    assert ok1 is False
    assert "未发现遥测心跳" in reason1

    # 2. 健康设备放行
    record_device_telemetry(
        device_id="dev_healthy",
        platform="ios",
        battery_temp_c=30.0,
        battery_level=80,
        current_concurrency=0,
        max_concurrency=2,
    )
    ok2, reason2 = is_device_eligible_for_dispatch("dev_healthy")
    assert ok2 is True
    assert "允许派发调度" in reason2

    # 3. 过热设备阻断
    record_device_telemetry(
        device_id="dev_hot",
        platform="android",
        battery_temp_c=43.5,
        battery_level=90,
    )
    ok3, reason3 = is_device_eligible_for_dispatch("dev_hot")
    assert ok3 is False
    assert "设备过热" in reason3

    # 4. 并发满载阻断
    record_device_telemetry(
        device_id="dev_full",
        platform="ios",
        battery_temp_c=34.0,
        battery_level=80,
        current_concurrency=2,
        max_concurrency=2,
    )
    ok4, reason4 = is_device_eligible_for_dispatch("dev_full")
    assert ok4 is False
    assert "已达到并发上限" in reason4
