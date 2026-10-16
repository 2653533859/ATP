"""全链路压测阶梯加压曲线与拐点检测器单元测试 (T4.1)。"""

from __future__ import annotations

import pytest
from app.services.step_load_throughput_knee_detector import (
    PerformanceZone,
    clear_throughput_knee_store,
    detect_throughput_knee_and_cliff,
    get_throughput_knee_report,
    list_throughput_knee_reports,
)


@pytest.fixture(autouse=True)
def _reset_knee_state():
    clear_throughput_knee_store()
    yield
    clear_throughput_knee_store()


def test_detect_throughput_knee_and_cliff_lifecycle():
    """测试拟合阶梯加压曲线，准确定位 Knee 拐点 (2000 VU) 与 Cliff 崩溃点 (3000 VU)。"""
    samples = [
        # 1. 线性最优区
        {"concurrency_threads": 500, "measured_tps": 2000.0, "avg_latency_ms": 25.0, "p99_latency_ms": 50.0},
        {"concurrency_threads": 1000, "measured_tps": 3800.0, "avg_latency_ms": 35.0, "p99_latency_ms": 70.0},
        # 2. 拐点 (Knee Point): 达到峰值 4800 TPS
        {"concurrency_threads": 2000, "measured_tps": 4800.0, "avg_latency_ms": 65.0, "p99_latency_ms": 140.0},
        # 3. 饱和区
        {"concurrency_threads": 2500, "measured_tps": 4700.0, "avg_latency_ms": 120.0, "p99_latency_ms": 280.0},
        # 4. 崩溃点 (Cliff Point): TPS 跌落至 3200 (跌幅 > 15%), P99 飙升, 错误率激增
        {
            "concurrency_threads": 3000,
            "measured_tps": 3200.0,
            "avg_latency_ms": 450.0,
            "p99_latency_ms": 1200.0,
            "error_rate_pct": 8.5,
        },
    ]

    report = detect_throughput_knee_and_cliff(scenario_name="checkout_step_load", samples=samples)

    assert report.total_steps_count == 5
    assert report.peak_tps == 4800.0
    assert report.knee_point_concurrency == 2000
    assert report.knee_point_tps == 4800.0
    assert report.cliff_point_concurrency == 3000
    assert report.recommended_safe_concurrency == 1500  # 2000 * 0.75 = 1500

    # 验证区间划分
    zones = [s.zone for s in report.step_samples]
    assert zones[0] == PerformanceZone.OPTIMAL_ZONE
    assert zones[1] == PerformanceZone.OPTIMAL_ZONE
    assert zones[2] == PerformanceZone.SATURATION_ZONE
    assert zones[4] == PerformanceZone.SATURATION_ZONE

    assert any("4800.0 TPS" in adv for adv in report.capacity_planning_advice)

    saved = get_throughput_knee_report(report.report_id)
    assert saved is not None
    assert saved.report_id == report.report_id
    assert len(list_throughput_knee_reports()) == 1


def test_detect_throughput_knee_no_cliff():
    """测试高可用系统未探明崩溃点。"""
    samples = [
        {"concurrency_threads": 100, "measured_tps": 500.0},
        {"concurrency_threads": 200, "measured_tps": 1000.0},
    ]

    report = detect_throughput_knee_and_cliff(scenario_name="robust_flow", samples=samples)
    assert report.peak_tps == 1000.0
    assert report.cliff_point_concurrency is None
    assert report.knee_point_concurrency == 200
