"""Multi-Dimensional Performance Comparison and Regression-Based Capacity Forecasting (Q3.3).

Provides:
1. Multi-run cross-sectional performance comparison matrix with scaling efficiency (RPS / VU).
2. Pure-Python linear and 2nd-degree polynomial regression fitting with R^2 evaluation.
3. Capacity forecasting: predicting maximum safe concurrency and RPS limit based on SLA thresholds.
4. Knee point (saturation inflection) detection and capacity planning recommendations.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
import logging
import math
from typing import Any

logger = logging.getLogger(__name__)


def _extract_number(val: Any) -> float | None:
    if val is None or isinstance(val, bool):
        return None
    try:
        num = float(val)
        return num if not (math.isnan(num) or math.isinf(num)) else None
    except (ValueError, TypeError):
        return None


def _extract_run_point(run: Mapping[str, Any]) -> dict[str, Any]:
    raw_summary = run.get("summary")
    summary: Mapping[str, Any] = raw_summary if isinstance(raw_summary, Mapping) else {}
    raw_options = run.get("options_snapshot")
    options: Mapping[str, Any] = raw_options if isinstance(raw_options, Mapping) else {}

    # Extract concurrency / load
    concurrency = (
        _extract_number(options.get("target_vus"))
        or _extract_number(options.get("vus"))
        or _extract_number(summary.get("vus"))
        or _extract_number(summary.get("load"))
        or _extract_number(summary.get("concurrency"))
    )

    rps = _extract_number(summary.get("rps"))
    p95_ms = _extract_number(summary.get("p95_ms"))
    p99_ms = _extract_number(summary.get("p99_ms"))
    avg_latency_ms = _extract_number(summary.get("avg_latency_ms")) or _extract_number(summary.get("mean_ms"))
    error_rate = _extract_number(summary.get("error_rate")) or 0.0

    scaling_efficiency = (
        round(rps / concurrency, 3) if (concurrency is not None and concurrency > 0 and rps is not None) else None
    )

    return {
        "run_id": run.get("id"),
        "status": str(run.get("status")),
        "created_at": str(run.get("created_at") or ""),
        "concurrency": concurrency,
        "rps": rps,
        "p95_ms": p95_ms,
        "p99_ms": p99_ms,
        "avg_latency_ms": avg_latency_ms,
        "error_rate": error_rate,
        "scaling_efficiency": scaling_efficiency,
    }


def build_multi_run_comparison(runs: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    """Build a cross-sectional comparison matrix across multiple performance runs."""
    points = [_extract_run_point(r) for r in runs]
    # Filter points with valid concurrency and rps
    valid_points = [p for p in points if p["concurrency"] is not None and p["rps"] is not None]
    valid_points.sort(key=lambda p: float(p["concurrency"]))

    best_rps_point = max(valid_points, key=lambda p: float(p["rps"]), default=None)
    best_efficiency_point = max(
        [p for p in valid_points if p["scaling_efficiency"] is not None],
        key=lambda p: float(p["scaling_efficiency"]),
        default=None,
    )

    return {
        "total_runs": len(runs),
        "valid_points_count": len(valid_points),
        "comparison_matrix": valid_points,
        "best_throughput": {
            "run_id": best_rps_point["run_id"] if best_rps_point else None,
            "max_rps": best_rps_point["rps"] if best_rps_point else None,
            "at_concurrency": best_rps_point["concurrency"] if best_rps_point else None,
        },
        "peak_efficiency": {
            "run_id": best_efficiency_point["run_id"] if best_efficiency_point else None,
            "scaling_efficiency": best_efficiency_point["scaling_efficiency"] if best_efficiency_point else None,
            "at_concurrency": best_efficiency_point["concurrency"] if best_efficiency_point else None,
        },
    }


def fit_linear_regression(x_vals: list[float], y_vals: list[float]) -> dict[str, Any]:
    """Fit 1st-degree linear model y = slope * x + intercept."""
    n = len(x_vals)
    if n < 2:
        return {"slope": 0.0, "intercept": 0.0, "r_squared": 0.0, "valid": False}

    mean_x = sum(x_vals) / n
    mean_y = sum(y_vals) / n

    numerator = sum((x_vals[i] - mean_x) * (y_vals[i] - mean_y) for i in range(n))
    denominator = sum((x_vals[i] - mean_x) ** 2 for i in range(n))

    if abs(denominator) < 1e-9:
        return {"slope": 0.0, "intercept": mean_y, "r_squared": 0.0, "valid": False}

    slope = numerator / denominator
    intercept = mean_y - slope * mean_x

    # Calculate R^2
    ss_tot = sum((y_vals[i] - mean_y) ** 2 for i in range(n))
    ss_res = sum((y_vals[i] - (slope * x_vals[i] + intercept)) ** 2 for i in range(n))
    r_squared = 1.0 - (ss_res / ss_tot) if ss_tot > 1e-9 else 1.0
    r_squared = max(0.0, min(1.0, r_squared))

    return {
        "slope": round(slope, 5),
        "intercept": round(intercept, 4),
        "r_squared": round(r_squared, 4),
        "valid": True,
    }


def _solve_3x3(matrix: list[list[float]], vector: list[float]) -> list[float] | None:
    """Gaussian elimination with partial pivoting for a 3x3 linear system."""
    a = [row[:] for row in matrix]
    b = vector[:]
    n = 3

    for i in range(n):
        # Pivot
        max_row = i
        for k in range(i + 1, n):
            if abs(a[k][i]) > abs(a[max_row][i]):
                max_row = k
        a[i], a[max_row] = a[max_row], a[i]
        b[i], b[max_row] = b[max_row], b[i]

        if abs(a[i][i]) < 1e-12:
            return None  # Singular matrix

        for k in range(i + 1, n):
            factor = a[k][i] / a[i][i]
            for j in range(i, n):
                a[k][j] -= factor * a[i][j]
            b[k] -= factor * b[i]

    # Back substitution
    x = [0.0] * n
    for i in range(n - 1, -1, -1):
        s = sum(a[i][j] * x[j] for j in range(i + 1, n))
        x[i] = (b[i] - s) / a[i][i]

    return x


def fit_polynomial_regression_deg2(x_vals: list[float], y_vals: list[float]) -> dict[str, Any]:
    """Fit 2nd-degree polynomial model y = a*x^2 + b*x + c."""
    n = len(x_vals)
    if n < 3:
        # Fallback to linear if fewer than 3 samples
        lin = fit_linear_regression(x_vals, y_vals)
        return {
            "a": 0.0,
            "b": lin["slope"],
            "c": lin["intercept"],
            "r_squared": lin["r_squared"],
            "valid": lin["valid"],
            "model_type": "linear_fallback",
        }

    sum_x = sum(x_vals)
    sum_x2 = sum(x**2 for x in x_vals)
    sum_x3 = sum(x**3 for x in x_vals)
    sum_x4 = sum(x**4 for x in x_vals)

    sum_y = sum(y_vals)
    sum_xy = sum(x_vals[i] * y_vals[i] for i in range(n))
    sum_x2y = sum((x_vals[i] ** 2) * y_vals[i] for i in range(n))

    # Matrix for [c, b, a]^T:
    # [ n,       sum_x,  sum_x2 ] [c]   [sum_y  ]
    # [ sum_x,   sum_x2, sum_x3 ] [b] = [sum_xy ]
    # [ sum_x2,  sum_x3, sum_x4 ] [a]   [sum_x2y]
    matrix = [
        [float(n), sum_x, sum_x2],
        [sum_x, sum_x2, sum_x3],
        [sum_x2, sum_x3, sum_x4],
    ]
    vector = [sum_y, sum_xy, sum_x2y]

    solution = _solve_3x3(matrix, vector)
    if solution is None:
        lin = fit_linear_regression(x_vals, y_vals)
        return {
            "a": 0.0,
            "b": lin["slope"],
            "c": lin["intercept"],
            "r_squared": lin["r_squared"],
            "valid": lin["valid"],
            "model_type": "linear_fallback",
        }

    c, b, a = solution

    mean_y = sum_y / n
    ss_tot = sum((y - mean_y) ** 2 for y in y_vals)
    ss_res = sum((y_vals[i] - (a * (x_vals[i] ** 2) + b * x_vals[i] + c)) ** 2 for i in range(n))
    r_squared = 1.0 - (ss_res / ss_tot) if ss_tot > 1e-9 else 1.0
    r_squared = max(0.0, min(1.0, r_squared))

    return {
        "a": round(a, 6),
        "b": round(b, 5),
        "c": round(c, 4),
        "r_squared": round(r_squared, 4),
        "valid": True,
        "model_type": "polynomial_deg2",
    }


def forecast_cluster_capacity(
    runs: Sequence[Mapping[str, Any]],
    *,
    sla_max_p95_ms: float = 500.0,
    sla_max_error_rate: float = 0.01,
    min_samples: int = 3,
) -> dict[str, Any]:
    """Forecast maximum safe concurrency capacity and RPS limits based on regression models."""
    comparison = build_multi_run_comparison(runs)
    points = comparison["comparison_matrix"]

    # Filter points where status is success or valid
    data_points = [
        p
        for p in points
        if p["concurrency"] is not None
        and p["rps"] is not None
        and p["p95_ms"] is not None
        and float(p["error_rate"]) <= sla_max_error_rate
    ]

    if len(data_points) < min_samples:
        return {
            "status": "insufficient_data",
            "message": f"有效达标压测轮次不足（需至少 {min_samples} 轮满足错误率 <= {sla_max_error_rate * 100}% 的测试，当前只有 {len(data_points)} 轮）",
            "comparison": comparison,
            "capacity_limit": None,
        }

    x_vus = [float(p["concurrency"]) for p in data_points]
    y_rps = [float(p["rps"]) for p in data_points]
    y_p95 = [float(p["p95_ms"]) for p in data_points]

    # 1. Fit Concurrency -> RPS (Linear)
    rps_model = fit_linear_regression(x_vus, y_rps)

    # 2. Fit Concurrency -> P95 Latency (Polynomial Degree 2)
    p95_model = fit_polynomial_regression_deg2(x_vus, y_p95)

    # 3. Detect Knee Point in empirical points
    # Knee point: the point with peak efficiency or where RPS growth rate sharply drops
    knee_point: dict[str, Any] | None = None
    for i in range(1, len(data_points)):
        delta_vu = data_points[i]["concurrency"] - data_points[i - 1]["concurrency"]
        delta_rps = data_points[i]["rps"] - data_points[i - 1]["rps"]
        marginal_rps_per_vu = delta_rps / max(delta_vu, 1.0)
        # If marginal gain falls below 20% of first step slope or turns negative
        initial_slope = max(rps_model["slope"], 0.1)
        if marginal_rps_per_vu < 0.2 * initial_slope or delta_rps < 0:
            knee_point = data_points[i - 1]
            break

    if knee_point is None and data_points:
        knee_point = comparison["peak_efficiency"]

    # 4. Solve for Capacity Limit where predicted P95 == sla_max_p95_ms
    # Equation: a*x^2 + b*x + (c - sla_max_p95_ms) = 0
    a = p95_model.get("a", 0.0)
    b = p95_model.get("b", 0.0)
    c = p95_model.get("c", 0.0)
    c_prime = c - sla_max_p95_ms

    predicted_max_concurrency: float | None = None

    if abs(a) > 1e-9:
        discriminant = b**2 - 4 * a * c_prime
        if discriminant >= 0:
            root1 = (-b + math.sqrt(discriminant)) / (2 * a)
            root2 = (-b - math.sqrt(discriminant)) / (2 * a)
            positive_roots = [r for r in (root1, root2) if r > max(x_vus[0], 0)]
            if positive_roots:
                predicted_max_concurrency = min(positive_roots)
    elif abs(b) > 1e-9:
        root = -c_prime / b
        if root > 0:
            predicted_max_concurrency = root

    # Cap projection within 3x of maximum tested concurrency to avoid reckless extrapolation
    max_tested_vu = max(x_vus)
    if predicted_max_concurrency is not None:
        predicted_max_concurrency = round(min(predicted_max_concurrency, max_tested_vu * 3.0), 1)
        predicted_max_rps = round(max(0.0, rps_model["slope"] * predicted_max_concurrency + rps_model["intercept"]), 1)
    else:
        # Fallback to max tested concurrency
        predicted_max_concurrency = float(max_tested_vu)
        predicted_max_rps = float(max(y_rps))

    # Overall confidence rating based on models' R^2
    avg_r2 = (rps_model["r_squared"] + p95_model["r_squared"]) / 2.0
    if avg_r2 >= 0.85 and len(data_points) >= 4:
        confidence = "High"
    elif avg_r2 >= 0.65:
        confidence = "Medium"
    else:
        confidence = "Low"

    # Actionable capacity advice
    advice = (
        f"在 P95 响应延迟不超过 {sla_max_p95_ms}ms 且错误率低于 {sla_max_error_rate * 100}% 的 SLA 约束下，"
        f"预测当前集群最大安全承载并发上限为 {int(predicted_max_concurrency)} VU，"
        f"预估峰值吞吐量为 {int(predicted_max_rps)} RPS。"
    )
    if knee_point and knee_point.get("concurrency"):
        advice += f" 性能饱和拐点位于 {knee_point['concurrency']} VU 附近，超过此区间后边际收益递减并伴随延迟剧增。"

    return {
        "status": "ready",
        "sample_count": len(data_points),
        "sla_criteria": {
            "max_p95_ms": sla_max_p95_ms,
            "max_error_rate": sla_max_error_rate,
        },
        "regression_models": {
            "rps_linear": rps_model,
            "p95_polynomial": p95_model,
            "confidence": confidence,
            "avg_r_squared": round(avg_r2, 4),
        },
        "capacity_limit": {
            "max_safe_concurrency": predicted_max_concurrency,
            "predicted_max_rps": predicted_max_rps,
            "knee_point": knee_point,
        },
        "recommendation": advice,
        "comparison": comparison,
    }
