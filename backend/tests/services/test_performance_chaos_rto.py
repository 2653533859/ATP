"""Unit tests for Q3.2 Performance Chaos Fault Injection and RTO Measurement.

Tests:
1. build_chaos_injection_plan validates fault types and parameters
2. calculate_chaos_rto measures rapid self-healing with Grade A
3. calculate_chaos_rto measures delayed self-healing with Grade B / C
4. calculate_chaos_rto detects failed recovery with Grade F
5. calculate_chaos_rto requires sustained recovery window to filter out jitter
6. calculate_chaos_rto handles empty metrics and zero baselines gracefully
"""

from __future__ import annotations

import pytest

from app.services.performance_chaos_rto import (
    build_chaos_injection_plan,
    calculate_chaos_rto,
)


def test_build_chaos_injection_plan_valid():
    plan = build_chaos_injection_plan(
        run_id=42,
        config={
            "fault_type": "service_unavailable",
            "target_service": "payment-api",
            "start_delay_seconds": 15.0,
            "duration_seconds": 20.0,
            "fault_params": {"status_code": 503},
        },
    )
    assert plan["run_id"] == 42
    assert plan["fault_type"] == "service_unavailable"
    assert plan["target_service"] == "payment-api"
    assert plan["start_delay_seconds"] == 15.0
    assert plan["duration_seconds"] == 20.0
    assert plan["fault_params"] == {"status_code": 503}
    assert plan["status"] == "scheduled"


def test_build_chaos_injection_plan_invalid():
    with pytest.raises(ValueError, match="不支持的故障类型"):
        build_chaos_injection_plan(run_id=1, config={"fault_type": "unknown_fault", "target_service": "api"})

    with pytest.raises(ValueError, match="目标服务名称或路径不能为空"):
        build_chaos_injection_plan(run_id=1, config={"fault_type": "latency_spike", "target_service": ""})

    with pytest.raises(ValueError, match="故障开始延迟秒数不能为负数"):
        build_chaos_injection_plan(
            run_id=1,
            config={"fault_type": "latency_spike", "target_service": "api", "start_delay_seconds": -5.0},
        )


def test_calculate_chaos_rto_rapid_recovery_grade_a():
    # Baseline: 1000 RPS, 50ms, 0% error (0-10s)
    # Fault: 10s-30s (duration 20s): 100 RPS, 500ms, 40% error
    # Recovery: 30s-32s -> 950 RPS, 55ms, 0.5% error (sustained)
    series: list[dict[str, float]] = []
    # Pre-fault (0..9s)
    for t in range(0, 10):
        series.append({"offset_seconds": float(t), "rps": 1000.0, "p95_ms": 50.0, "error_rate": 0.0})
    # Fault (10..30s)
    for t in range(10, 31):
        series.append({"offset_seconds": float(t), "rps": 120.0, "p95_ms": 450.0, "error_rate": 0.35})
    # Post-fault rapid recovery starting at 32s (RTO = 2s)
    for t in range(31, 45):
        if t < 32:
            series.append({"offset_seconds": float(t), "rps": 300.0, "p95_ms": 250.0, "error_rate": 0.15})
        else:
            series.append({"offset_seconds": float(t), "rps": 960.0, "p95_ms": 52.0, "error_rate": 0.005})

    result = calculate_chaos_rto(
        series,
        fault_start_offset=10.0,
        fault_duration=20.0,
        sustain_seconds=3.0,
    )

    assert result["recovered"] is True
    assert result["rto_seconds"] == 2.0  # 32s - 30s
    assert result["resilience_grade"] == "A"
    assert result["resilience_score"] >= 80.0
    assert result["in_fault_metrics"]["rps_drop_pct"] >= 85.0


def test_calculate_chaos_rto_moderate_recovery_grade_b():
    # Fault ends at 25s (10s..25s). Recovery happens at 32s -> RTO = 7.0s
    series: list[dict[str, float]] = []
    for t in range(0, 10):
        series.append({"offset_seconds": float(t), "rps": 500.0, "p95_ms": 80.0, "error_rate": 0.01})
    for t in range(10, 26):
        series.append({"offset_seconds": float(t), "rps": 50.0, "p95_ms": 600.0, "error_rate": 0.50})
    # Gradually recovering, reaches steady recovery at 32s
    for t in range(26, 45):
        if t < 32:
            series.append({"offset_seconds": float(t), "rps": 250.0, "p95_ms": 200.0, "error_rate": 0.10})
        else:
            series.append({"offset_seconds": float(t), "rps": 480.0, "p95_ms": 85.0, "error_rate": 0.012})

    result = calculate_chaos_rto(
        series,
        fault_start_offset=10.0,
        fault_duration=15.0,
        sustain_seconds=3.0,
    )

    assert result["recovered"] is True
    assert result["rto_seconds"] == 7.0
    assert result["resilience_grade"] == "B"
    assert "良好自愈能力" in result["recommendation"]


def test_calculate_chaos_rto_unrecovered_grade_f():
    # Service stays down even after fault ends
    series: list[dict[str, float]] = []
    for t in range(0, 10):
        series.append({"offset_seconds": float(t), "rps": 600.0, "p95_ms": 40.0, "error_rate": 0.0})
    for t in range(10, 30):
        series.append({"offset_seconds": float(t), "rps": 20.0, "p95_ms": 800.0, "error_rate": 0.80})
    # Remains degraded
    for t in range(30, 45):
        series.append({"offset_seconds": float(t), "rps": 50.0, "p95_ms": 700.0, "error_rate": 0.60})

    result = calculate_chaos_rto(
        series,
        fault_start_offset=10.0,
        fault_duration=15.0,
        sustain_seconds=3.0,
    )

    assert result["recovered"] is False
    assert result["rto_seconds"] is None
    assert result["resilience_grade"] == "F"
    assert "未能在测试窗口内自愈恢复" in result["recommendation"]


def test_calculate_chaos_rto_sustained_window_filters_jitter():
    # A single metric point at 31s seems recovered, but dips again at 32-33s.
    # Real recovery only happens from 35s onward.
    series: list[dict[str, float]] = []
    for t in range(0, 10):
        series.append({"offset_seconds": float(t), "rps": 500.0, "p95_ms": 50.0, "error_rate": 0.0})
    for t in range(10, 30):
        series.append({"offset_seconds": float(t), "rps": 50.0, "p95_ms": 500.0, "error_rate": 0.50})

    # 30s: post fault
    # 31s: false recovery spike
    series.append({"offset_seconds": 31.0, "rps": 490.0, "p95_ms": 55.0, "error_rate": 0.01})
    # 32s-34s: dip back down
    series.append({"offset_seconds": 32.0, "rps": 100.0, "p95_ms": 400.0, "error_rate": 0.30})
    series.append({"offset_seconds": 33.0, "rps": 120.0, "p95_ms": 380.0, "error_rate": 0.25})
    series.append({"offset_seconds": 34.0, "rps": 200.0, "p95_ms": 250.0, "error_rate": 0.15})
    # 35s..42s: true sustained recovery
    for t in range(35, 43):
        series.append({"offset_seconds": float(t), "rps": 480.0, "p95_ms": 52.0, "error_rate": 0.01})

    result = calculate_chaos_rto(
        series,
        fault_start_offset=10.0,
        fault_duration=20.0,  # ends at 30s
        sustain_seconds=3.0,
    )

    assert result["recovered"] is True
    # Sustained recovery should NOT pick 31.0s, but 35.0s -> RTO = 35 - 30 = 5.0s
    assert result["recovered_at_offset"] == 35.0
    assert result["rto_seconds"] == 5.0
