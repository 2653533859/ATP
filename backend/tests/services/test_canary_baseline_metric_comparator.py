"""金丝雀与基线双轨指标实时对比推演器单测 (T1.2)"""

from __future__ import annotations

from app.services.canary_baseline_metric_comparator import (
    MetricDeviationVerdict,
    TrackMetricsSample,
    compare_canary_and_baseline_tracks,
)


def test_compare_tracks_conformant():
    base = TrackMetricsSample(
        track_name="baseline",
        version_tag="v1.0.0",
        total_requests=10000,
        error_requests=10,
        error_rate_pct=0.1,
        success_rate_pct=99.9,
        p99_latency_ms=100.0,
        avg_latency_ms=35.0,
        cpu_usage_pct=30.0,
    )
    canary = TrackMetricsSample(
        track_name="canary",
        version_tag="v1.1.0-rc1",
        total_requests=1000,
        error_requests=2,
        error_rate_pct=0.2,
        success_rate_pct=99.8,
        p99_latency_ms=105.0,
        avg_latency_ms=36.0,
        cpu_usage_pct=32.0,
    )

    report = compare_canary_and_baseline_tracks(base, canary, target_service="payment-service")
    assert report.overall_verdict == MetricDeviationVerdict.CONFORMANT
    assert report.error_rate_diff_pct == 0.1
    assert round(report.latency_p99_ratio, 2) == 1.05
    assert len(report.findings) >= 2


def test_compare_tracks_warning_degraded():
    base = TrackMetricsSample(
        track_name="baseline",
        version_tag="v1.0.0",
        total_requests=5000,
        error_requests=10,
        error_rate_pct=0.2,
        success_rate_pct=99.8,
        p99_latency_ms=150.0,
        avg_latency_ms=40.0,
    )
    # 错误率微升 0.8% (处于 0.5%~1.5% 预警带)
    canary = TrackMetricsSample(
        track_name="canary",
        version_tag="v1.1.0-beta",
        total_requests=500,
        error_requests=5,
        error_rate_pct=1.0,
        success_rate_pct=99.0,
        p99_latency_ms=170.0,
        avg_latency_ms=45.0,
    )

    report = compare_canary_and_baseline_tracks(base, canary, target_service="order-service")
    assert report.overall_verdict == MetricDeviationVerdict.WARNING_DEGRADED
    assert any("轻度上升" in f for f in report.findings)


def test_compare_tracks_breached_deficit_by_error():
    base = TrackMetricsSample(
        track_name="baseline",
        version_tag="v1.0.0",
        total_requests=10000,
        error_requests=5,
        error_rate_pct=0.05,
        success_rate_pct=99.95,
        p99_latency_ms=120.0,
        avg_latency_ms=30.0,
    )
    # 错误率突增至 4.0%
    canary = TrackMetricsSample(
        track_name="canary",
        version_tag="v1.2.0-bad",
        total_requests=1000,
        error_requests=40,
        error_rate_pct=4.0,
        success_rate_pct=96.0,
        p99_latency_ms=130.0,
        avg_latency_ms=35.0,
    )

    report = compare_canary_and_baseline_tracks(base, canary, target_service="auth-service")
    assert report.overall_verdict == MetricDeviationVerdict.BREACHED_DEFICIT
    assert any("错误率严重击穿" in f for f in report.findings)


def test_compare_tracks_breached_deficit_by_latency():
    base = TrackMetricsSample(
        track_name="baseline",
        version_tag="v2.0",
        total_requests=8000,
        error_requests=8,
        error_rate_pct=0.1,
        success_rate_pct=99.9,
        p99_latency_ms=100.0,
        avg_latency_ms=30.0,
    )
    # 延迟飙升至 2.5x
    canary = TrackMetricsSample(
        track_name="canary",
        version_tag="v2.1",
        total_requests=800,
        error_requests=1,
        error_rate_pct=0.12,
        success_rate_pct=99.88,
        p99_latency_ms=250.0,
        avg_latency_ms=80.0,
    )

    report = compare_canary_and_baseline_tracks(base, canary, target_service="inventory-service")
    assert report.overall_verdict == MetricDeviationVerdict.BREACHED_DEFICIT
    assert report.latency_p99_ratio == 2.5
    assert any("P99延迟严重退化" in f for f in report.findings)

    d = report.to_dict()
    assert d["overall_verdict"] == "BREACHED_DEFICIT"
    assert d["latency_p99_ratio"] == 2.5
