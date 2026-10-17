"""动态反压与队列吞吐自适应均衡器单测 (T2.3)"""

from __future__ import annotations

import pytest

from app.services.dynamic_backpressure_balancer import (
    BackpressureLevel,
    adjust_backpressure_window,
    calculate_fleet_capacity_and_saturation,
    clear_backpressure_state,
    get_current_backpressure_status,
    list_backpressure_snapshots,
)
from app.services.fleet_health_telemetry import (
    clear_fleet_telemetry,
    record_device_telemetry,
)


@pytest.fixture(autouse=True)
def clean_state():
    clear_fleet_telemetry()
    clear_backpressure_state()
    yield
    clear_fleet_telemetry()
    clear_backpressure_state()


def test_additive_increase_under_healthy_load():
    # 注册两台空闲设备，总容量 4，已用并发 0 (饱和度 0.0)
    record_device_telemetry("dev_1", "ios", 30.0, 90, current_concurrency=0, max_concurrency=2)
    record_device_telemetry("dev_2", "android", 31.0, 85, current_concurrency=0, max_concurrency=2)

    total_cap, used_con, sat, _ = calculate_fleet_capacity_and_saturation()
    assert total_cap == 4
    assert used_con == 0
    assert sat == 0.0

    # 初始窗口=10，健康状况下触发加法递增 (+2 -> 12)
    snap1 = adjust_backpressure_window(queue_depth=5, average_wait_latency_ms=100.0)
    assert snap1.level == BackpressureLevel.NORMAL
    assert snap1.current_window_size == 12
    assert "加法递增" in snap1.action_description


def test_multiplicative_decrease_under_high_saturation():
    # 注册两台设备，总容量 4，已用并发 4 (饱和度 1.0 >= 0.85)
    record_device_telemetry("dev_full_1", "ios", 35.0, 80, current_concurrency=2, max_concurrency=2)
    record_device_telemetry("dev_full_2", "ios", 36.0, 75, current_concurrency=2, max_concurrency=2)

    # 初始窗口=10，重度负载下触发乘法递减 (*0.6 -> 6)
    snap_heavy = adjust_backpressure_window(queue_depth=15, average_wait_latency_ms=800.0)
    assert snap_heavy.level == BackpressureLevel.HEAVY_BACKPRESSURE
    assert snap_heavy.current_window_size == 6
    assert "乘法递减" in snap_heavy.action_description


def test_queue_overflow_rejection():
    # 模拟极端洪峰: 排队深度达到 120 (超过默认容限 100)
    snap_overflow = adjust_backpressure_window(queue_depth=120)
    assert snap_overflow.level == BackpressureLevel.OVERFLOW_REJECTION
    assert snap_overflow.current_window_size == 2  # 降至最小安全窗口
    assert "溢出熔断拒绝" in snap_overflow.action_description


def test_status_snapshot_and_listing():
    record_device_telemetry("dev_snap_01", "ios", 32.0, 80, current_concurrency=0, max_concurrency=2)
    snap = adjust_backpressure_window(queue_depth=2)

    assert len(list_backpressure_snapshots()) == 1
    current = get_current_backpressure_status()
    assert current.current_window_size == snap.current_window_size

    d = snap.to_dict()
    assert d["snapshot_id"].startswith("snap_bp_")
    assert d["level"] in ("NORMAL", "LIGHT_THROTTLING", "HEAVY_BACKPRESSURE")
