"""Unit tests for P3.2 Distributed performance metric aggregation and baseline comparison.

Tests:
1. aggregate_distributed_timeseries_samples:
   - Aggregates real-time time-series metric samples across multiple K8s Pods
   - Sums throughput (TPS, RPS, requests)
   - Evaluates peak response times (p50, p90, p95, p99)
   - Averages error rates across shards
2. build_baseline_comparison:
   - Determines quality gate verdicts (passed, regression, improvement)
   - Flags severe regressions on throughput drops (>15%), latency increases (>20%), or error spikes (>2%)
3. Schema serialization via PerformanceBaselineComparisonOut
"""

from __future__ import annotations

from app.schemas.performance import PerformanceBaselineComparisonOut
from app.services.performance_report import build_baseline_comparison
from app.services.performance_sharding import aggregate_distributed_timeseries_samples


def test_aggregate_distributed_timeseries_samples_multi_pod():
    pod_samples = [
        # Pod 0 at T1
        {
            "captured_at": "2026-10-15T10:00:00Z",
            "shard_id": "pod-0",
            "rps": 120.5,
            "tps": 118.0,
            "requests": 1200,
            "p50_ms": 15.0,
            "p90_ms": 25.0,
            "p95_ms": 32.0,
            "p99_ms": 50.0,
            "error_rate": 0.01,
        },
        # Pod 1 at T1
        {
            "captured_at": "2026-10-15T10:00:00Z",
            "shard_id": "pod-1",
            "rps": 130.5,
            "tps": 122.0,
            "requests": 1300,
            "p50_ms": 18.0,
            "p90_ms": 28.0,
            "p95_ms": 40.0,
            "p99_ms": 65.0,
            "error_rate": 0.02,
        },
        # Pod 0 at T2
        {
            "captured_at": "2026-10-15T10:00:05Z",
            "shard_id": "pod-0",
            "rps": 150.0,
            "p95_ms": 35.0,
            "error_rate": 0.0,
        },
    ]

    aggregated = aggregate_distributed_timeseries_samples(pod_samples)
    assert len(aggregated) == 2

    # T1 aggregation (2 pods)
    t1 = aggregated[0]
    assert t1["captured_at"] == "2026-10-15T10:00:00Z"
    assert t1["shard_count"] == 2
    assert t1["rps"] == 251.0  # 120.5 + 130.5
    assert t1["tps"] == 240.0  # 118.0 + 122.0
    assert t1["requests"] == 2500.0  # 1200 + 1300
    assert t1["p50_ms"] == 18.0  # max(15, 18)
    assert t1["p95_ms"] == 40.0  # max(32, 40)
    assert t1["p99_ms"] == 65.0  # max(50, 65)
    assert t1["error_rate"] == 0.015  # (0.01 + 0.02) / 2

    # T2 aggregation (1 pod)
    t2 = aggregated[1]
    assert t2["captured_at"] == "2026-10-15T10:00:05Z"
    assert t2["shard_count"] == 1
    assert t2["rps"] == 150.0
    assert t2["p95_ms"] == 35.0
    assert t2["error_rate"] == 0.0


def test_aggregate_distributed_timeseries_samples_empty():
    assert aggregate_distributed_timeseries_samples([]) == []


def test_baseline_comparison_verdict_improvement():
    baseline = {"rps": 500, "p95_ms": 100, "p99_ms": 200, "error_rate": 0.01}
    current = {"rps": 600, "p95_ms": 80, "p99_ms": 150, "error_rate": 0.005}

    result = build_baseline_comparison(1, 2, baseline, current)
    assert result["verdict"] == "improvement"
    assert "显著提升" in str(result["summary_verdict"])

    parsed = PerformanceBaselineComparisonOut.model_validate(result)
    assert parsed.verdict == "improvement"


def test_baseline_comparison_verdict_severe_regression():
    baseline = {"rps": 1000, "p95_ms": 50, "p99_ms": 100, "error_rate": 0.005}
    # TPS dropped by 30%, p95 increased by 50%, error rate spiked
    current = {"rps": 700, "p95_ms": 75, "p99_ms": 160, "error_rate": 0.03}

    result = build_baseline_comparison(10, 11, baseline, current)
    assert result["verdict"] == "regression"
    assert "显著劣化" in str(result["summary_verdict"])

    parsed = PerformanceBaselineComparisonOut.model_validate(result)
    assert parsed.verdict == "regression"


def test_baseline_comparison_verdict_passed_within_tolerance():
    baseline = {"rps": 500, "p95_ms": 50, "p99_ms": 100, "error_rate": 0.01}
    # slight variance within tolerance (<15% drop, <20% latency increase, <2% error delta)
    current = {"rps": 490, "p95_ms": 52, "p99_ms": 102, "error_rate": 0.012}

    result = build_baseline_comparison(20, 21, baseline, current)
    assert result["verdict"] == "passed"
    assert "判定通过" in str(result["summary_verdict"])

    parsed = PerformanceBaselineComparisonOut.model_validate(result)
    assert parsed.verdict == "passed"
