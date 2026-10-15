"""Unit tests for Q3.3 Multi-Dimensional Performance Comparison and Capacity Forecasting.

Tests:
1. build_multi_run_comparison builds cross-sectional matrix and calculates scaling efficiency
2. fit_linear_regression fits 1st-degree slope, intercept, and R^2 accurately
3. fit_polynomial_regression_deg2 fits 2nd-degree curve and handles small sample fallbacks
4. forecast_cluster_capacity calculates maximum safe concurrency and RPS limits under SLA
5. forecast_cluster_capacity detects knee point (saturation inflection)
6. forecast_cluster_capacity handles insufficient samples gracefully
"""

from __future__ import annotations

from app.services.performance_capacity_forecaster import (
    build_multi_run_comparison,
    fit_linear_regression,
    fit_polynomial_regression_deg2,
    forecast_cluster_capacity,
)


def test_build_multi_run_comparison():
    runs = [
        {
            "id": 101,
            "status": "success",
            "options_snapshot": {"target_vus": 100},
            "summary": {"rps": 1000.0, "p95_ms": 40.0, "error_rate": 0.0},
        },
        {
            "id": 102,
            "status": "success",
            "options_snapshot": {"target_vus": 200},
            "summary": {"rps": 1900.0, "p95_ms": 65.0, "error_rate": 0.002},
        },
        {
            "id": 103,
            "status": "success",
            "options_snapshot": {"target_vus": 300},
            "summary": {"rps": 2400.0, "p95_ms": 120.0, "error_rate": 0.005},
        },
    ]

    res = build_multi_run_comparison(runs)
    assert res["total_runs"] == 3
    assert res["valid_points_count"] == 3
    matrix = res["comparison_matrix"]
    assert len(matrix) == 3

    # Check scaling efficiency: run 1 has 1000/100 = 10.0, run 2 has 1900/200 = 9.5
    assert matrix[0]["scaling_efficiency"] == 10.0
    assert matrix[1]["scaling_efficiency"] == 9.5

    assert res["best_throughput"]["run_id"] == 103
    assert res["best_throughput"]["max_rps"] == 2400.0

    assert res["peak_efficiency"]["run_id"] == 101
    assert res["peak_efficiency"]["scaling_efficiency"] == 10.0


def test_fit_linear_regression():
    # Exactly y = 2x + 10
    x = [10.0, 20.0, 30.0, 40.0, 50.0]
    y = [30.0, 50.0, 70.0, 90.0, 110.0]

    model = fit_linear_regression(x, y)
    assert model["valid"] is True
    assert abs(model["slope"] - 2.0) < 1e-4
    assert abs(model["intercept"] - 10.0) < 1e-4
    assert abs(model["r_squared"] - 1.0) < 1e-4

    # Degenerate case: single point
    assert fit_linear_regression([1.0], [2.0])["valid"] is False


def test_fit_polynomial_regression_deg2():
    # Quadratic curve: y = 0.01*x^2 + 0.5*x + 20
    x = [10.0, 20.0, 30.0, 40.0, 50.0]
    y = [0.01 * (v**2) + 0.5 * v + 20.0 for v in x]

    model = fit_polynomial_regression_deg2(x, y)
    assert model["valid"] is True
    assert model["model_type"] == "polynomial_deg2"
    assert abs(model["a"] - 0.01) < 1e-3
    assert abs(model["b"] - 0.5) < 1e-3
    assert abs(model["c"] - 20.0) < 1e-2
    assert model["r_squared"] > 0.99


def test_forecast_cluster_capacity_normal():
    # Simulate a realistic capacity test suite with 4 load steps:
    # 100 VU -> 1000 RPS, P95 50ms
    # 200 VU -> 1950 RPS, P95 70ms
    # 400 VU -> 3600 RPS, P95 140ms
    # 600 VU -> 4800 RPS, P95 280ms
    runs = [
        {
            "id": 1,
            "status": "success",
            "options_snapshot": {"target_vus": 100},
            "summary": {"rps": 1000.0, "p95_ms": 50.0, "error_rate": 0.0},
        },
        {
            "id": 2,
            "status": "success",
            "options_snapshot": {"target_vus": 200},
            "summary": {"rps": 1950.0, "p95_ms": 70.0, "error_rate": 0.001},
        },
        {
            "id": 3,
            "status": "success",
            "options_snapshot": {"target_vus": 400},
            "summary": {"rps": 3600.0, "p95_ms": 140.0, "error_rate": 0.002},
        },
        {
            "id": 4,
            "status": "success",
            "options_snapshot": {"target_vus": 600},
            "summary": {"rps": 4800.0, "p95_ms": 280.0, "error_rate": 0.003},
        },
    ]

    forecast = forecast_cluster_capacity(runs, sla_max_p95_ms=500.0, sla_max_error_rate=0.01)
    assert forecast["status"] == "ready"
    assert forecast["sample_count"] == 4
    assert forecast["regression_models"]["confidence"] in {"High", "Medium"}

    cap = forecast["capacity_limit"]
    # Safe concurrency must be greater than max tested (600) and within extrapolation bounds
    assert cap["max_safe_concurrency"] > 600.0
    assert cap["predicted_max_rps"] > 4800.0
    assert "最大安全承载并发上限" in forecast["recommendation"]


def test_forecast_cluster_capacity_detects_knee_point():
    # 100 VU -> 1000 RPS (gain 10 RPS/VU)
    # 200 VU -> 2000 RPS (gain 10 RPS/VU)
    # 300 VU -> 2500 RPS (gain 5 RPS/VU, starting to slow)
    # 400 VU -> 2550 RPS (gain 0.5 RPS/VU, knee point at 300 VU)
    runs = [
        {"id": 1, "status": "success", "summary": {"load": 100, "rps": 1000.0, "p95_ms": 40.0, "error_rate": 0.0}},
        {"id": 2, "status": "success", "summary": {"load": 200, "rps": 2000.0, "p95_ms": 50.0, "error_rate": 0.0}},
        {"id": 3, "status": "success", "summary": {"load": 300, "rps": 2500.0, "p95_ms": 110.0, "error_rate": 0.0}},
        {"id": 4, "status": "success", "summary": {"load": 400, "rps": 2550.0, "p95_ms": 320.0, "error_rate": 0.0}},
    ]

    forecast = forecast_cluster_capacity(runs, sla_max_p95_ms=600.0)
    assert forecast["status"] == "ready"
    knee = forecast["capacity_limit"]["knee_point"]
    assert knee is not None
    assert knee["concurrency"] in {200, 300}
    assert "性能饱和拐点" in forecast["recommendation"]


def test_forecast_cluster_capacity_insufficient_samples():
    runs = [
        {"id": 1, "status": "success", "summary": {"load": 100, "rps": 1000.0, "p95_ms": 40.0, "error_rate": 0.0}},
        # Exceeds error rate, so it will be disqualified
        {"id": 2, "status": "success", "summary": {"load": 200, "rps": 1500.0, "p95_ms": 50.0, "error_rate": 0.08}},
    ]

    forecast = forecast_cluster_capacity(runs, sla_max_error_rate=0.01, min_samples=3)
    assert forecast["status"] == "insufficient_data"
    assert "有效达标压测轮次不足" in forecast["message"]
    assert forecast["capacity_limit"] is None
