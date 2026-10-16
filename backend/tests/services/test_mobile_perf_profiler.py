"""Unit tests for D3.1 Mobile Performance Profiler Service."""

import pytest

from app.services.mobile_perf_profiler import (
    MobilePerfSessionConfig,
    PerformanceSamplePoint,
    get_perf_session_report,
    list_perf_sessions,
    record_perf_samples_batch,
    reset_mobile_perf_registry,
    start_perf_session,
    stop_perf_session,
)


@pytest.fixture(autouse=True)
def clean_registry():
    reset_mobile_perf_registry()
    yield
    reset_mobile_perf_registry()


def test_start_and_record_samples():
    config = MobilePerfSessionConfig(
        session_id="session_normal_01",
        device_serial="emulator-5554",
        package_name="com.example.shop",
    )
    start_perf_session(config)

    samples = [
        PerformanceSamplePoint(timestamp_sec=0.0, cpu_app_pct=15.0, cpu_total_pct=25.0, memory_pss_mb=120.0, fps=60.0),
        PerformanceSamplePoint(timestamp_sec=1.0, cpu_app_pct=18.0, cpu_total_pct=28.0, memory_pss_mb=122.0, fps=59.0),
        PerformanceSamplePoint(timestamp_sec=2.0, cpu_app_pct=20.0, cpu_total_pct=30.0, memory_pss_mb=121.0, fps=60.0),
    ]
    record_perf_samples_batch("session_normal_01", samples)

    report = stop_perf_session("session_normal_01")
    assert report.total_samples_count == 3
    assert report.summary["cpu_app_avg"] == pytest.approx(17.67, 0.05)
    assert report.summary["cpu_app_max"] == 20.0
    assert report.summary["memory_pss_max"] == 122.0
    assert report.summary["fps_avg"] == pytest.approx(59.7, 0.1)
    assert report.summary["has_memory_leak"] is False
    assert len(report.anomalies) == 0


def test_detect_memory_leak_slope():
    config = MobilePerfSessionConfig(
        session_id="session_leak_02",
        device_serial="device_hw_mate60",
        package_name="com.example.game",
    )
    start_perf_session(config)

    # 模拟内存以每秒 2MB (120MB/min) 线性单调上涨
    leak_samples = [
        PerformanceSamplePoint(
            timestamp_sec=float(i), cpu_app_pct=30.0, cpu_total_pct=40.0, memory_pss_mb=100.0 + i * 2.0, fps=58.0
        )
        for i in range(10)
    ]
    record_perf_samples_batch("session_leak_02", leak_samples)

    report = stop_perf_session("session_leak_02")
    assert report.summary["has_memory_leak"] is True
    assert report.summary["memory_growth_slope_mb_per_min"] > 100.0

    leak_anomaly = next((a for a in report.anomalies if a.anomaly_type == "MEMORY_LEAK_WARNING"), None)
    assert leak_anomaly is not None
    assert leak_anomaly.severity == "critical"
    assert "疑似存在内存泄露" in leak_anomaly.description


def test_detect_jank_and_frame_drop():
    config = MobilePerfSessionConfig(
        session_id="session_jank_03",
        device_serial="emulator-5554",
        package_name="com.example.feed",
    )
    start_perf_session(config)

    # 模拟严重掉帧：帧率仅 25 FPS，且每秒产生多个卡顿帧
    jank_samples = [
        PerformanceSamplePoint(
            timestamp_sec=float(i), cpu_app_pct=45.0, cpu_total_pct=60.0, memory_pss_mb=150.0, fps=25.0, jank_count=3
        )
        for i in range(6)
    ]
    record_perf_samples_batch("session_jank_03", jank_samples)

    report = stop_perf_session("session_jank_03")
    assert report.summary["has_jank_drops"] is True
    assert report.summary["fps_avg"] == 25.0
    assert report.summary["total_janks"] == 18

    jank_anomaly = next((a for a in report.anomalies if a.anomaly_type == "JANK_FRAME_DROP"), None)
    assert jank_anomaly is not None
    assert jank_anomaly.severity == "critical"


def test_detect_high_cpu_alert():
    config = MobilePerfSessionConfig(
        session_id="session_cpu_04",
        device_serial="emulator-5554",
        package_name="com.example.ai",
    )
    start_perf_session(config)

    cpu_samples = [
        PerformanceSamplePoint(
            timestamp_sec=float(i), cpu_app_pct=92.0, cpu_total_pct=98.0, memory_pss_mb=180.0, fps=60.0
        )
        for i in range(5)
    ]
    record_perf_samples_batch("session_cpu_04", cpu_samples)

    report = stop_perf_session("session_cpu_04")
    cpu_anomaly = next((a for a in report.anomalies if a.anomaly_type == "HIGH_CPU_ALERT"), None)
    assert cpu_anomaly is not None
    assert "92.0%" in cpu_anomaly.description


def test_list_sessions_and_error_handling():
    config = MobilePerfSessionConfig(
        session_id="session_list_05",
        device_serial="emulator-5554",
        package_name="com.example.app",
    )
    start_perf_session(config)

    sessions = list_perf_sessions()
    assert len(sessions) == 1
    assert get_perf_session_report("session_list_05") is not None

    with pytest.raises(ValueError, match="性能会话不存在"):
        stop_perf_session("non_existent_session_999")
