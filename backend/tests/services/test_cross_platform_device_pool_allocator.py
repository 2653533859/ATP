"""跨端移动设备统一分配器服务单测 (T2.3)"""

from __future__ import annotations

import pytest

from app.services.cross_platform_device_pool_allocator import (
    allocate_matching_device,
    clear_mock_android_devices,
    get_device_pool_capacity_summary,
    list_all_unified_devices,
    register_mock_android_device,
)
from app.services.ios_device_heartbeat_keeper import (
    clear_heartbeat_records,
    record_ios_heartbeat,
)
from app.services.ios_lease_scheduler import clear_ios_leases
from app.services.ios_tunnel_bridge import (
    clear_ios_tunnels,
    register_ios_tunnel,
)


@pytest.fixture(autouse=True)
def clean_state():
    clear_ios_tunnels()
    clear_heartbeat_records()
    clear_ios_leases()
    clear_mock_android_devices()
    yield
    clear_ios_tunnels()
    clear_heartbeat_records()
    clear_ios_leases()
    clear_mock_android_devices()


def test_cross_platform_device_pool_aggregation():
    # 1. 注册一台 iOS 设备
    ios_udid = "00008101-ALLOCATOR-IOS-01"
    register_ios_tunnel(
        udid=ios_udid,
        device_name="iPhone 15",
        model="iPhone15,4",
        ios_version="17.2",
        agent_id="mac_agent_01",
        agent_name="Mac-Mini",
    )
    record_ios_heartbeat(udid=ios_udid, agent_id="mac_agent_01", battery_level=98)

    # 2. 注册一台 Android 设备
    android_serial = "emulator-5554"
    register_mock_android_device(
        serial=android_serial,
        name="Pixel 8 Pro",
        model="Pixel 8",
        brand="Google",
        os_version="14.0",
        battery_level=85,
    )

    all_devs = list_all_unified_devices()
    assert len(all_devs) == 2

    platforms = {d.platform for d in all_devs}
    assert "ios" in platforms
    assert "android" in platforms

    # 3. 统计容量
    summary = get_device_pool_capacity_summary()
    assert summary["total_devices"] == 2
    assert summary["ios_devices_count"] == 1
    assert summary["android_devices_count"] == 1
    assert summary["idle_devices"] == 2


def test_allocate_matching_device_with_auto_lease():
    ios_udid = "00008101-ALLOCATOR-IOS-02"
    register_ios_tunnel(
        udid=ios_udid,
        device_name="iPhone 15 Pro",
        model="iPhone16,1",
        ios_version="17.4",
        agent_id="mac_agent_01",
        agent_name="Mac-Mini",
    )
    record_ios_heartbeat(udid=ios_udid, agent_id="mac_agent_01", battery_level=95)

    register_mock_android_device(
        serial="emulator-5556",
        name="Xiaomi 14",
        brand="Xiaomi",
        os_version="14.0",
    )

    # 1. 精确匹配 iOS 并自动加锁租约
    matched_ios = allocate_matching_device(
        platform="ios",
        brand="Apple",
        min_os_version="17.0",
        auto_lease=True,
        owner_id="pipeline_job_101",
        owner_label="CI-Runner-01",
    )
    assert matched_ios is not None
    assert matched_ios["raw_id"] == ios_udid
    assert matched_ios["platform"] == "ios"
    assert "lease_token" in matched_ios
    assert matched_ios["status"] == "BUSY"

    # 2. 匹配 Android 设备
    matched_android = allocate_matching_device(
        platform="android",
        brand="Xiaomi",
    )
    assert matched_android is not None
    assert matched_android["brand"] == "Xiaomi"
    assert matched_android["platform"] == "android"

    # 3. 不存在匹配机型时返回 None
    matched_none = allocate_matching_device(
        platform="ios",
        min_os_version="19.0",  # 不存在
    )
    assert matched_none is None
