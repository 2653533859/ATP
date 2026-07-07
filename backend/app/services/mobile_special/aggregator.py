"""Aggregators for mobile special metric samples and run summaries.

Takes raw samples collected during a run and computes:
  - Average and peak values for each metric type
  - Crash and ANR counts
  - Per-task-type summary JSON suitable for MobileSpecialRun.summary_json
"""

from typing import Any, Optional

from app.models.mobile_special import MetricType, TaskType


def aggregate_samples(samples: list[dict]) -> dict[str, Any]:
    """Aggregate a list of metric samples into summary statistics.

    Args:
        samples: List of sample dicts with keys:
            metric_type (str), metric_value (float), sample_time (datetime)

    Returns:
        Dict of metric_type -> {"avg": float, "max": float, "min": float, "count": int}
    """
    by_type: dict[str, list[float]] = {}

    for sample in samples:
        metric_type = sample.get("metric_type")
        if metric_type is None:
            continue
        if metric_type not in by_type:
            by_type[metric_type] = []
        by_type[metric_type].append(float(sample.get("metric_value", 0)))

    result = {}
    for metric_type, values in by_type.items():
        if values:
            result[metric_type] = {
                "avg": round(sum(values) / len(values), 2),
                "max": round(max(values), 2),
                "min": round(min(values), 2),
                "count": len(values),
            }

    return result


def compute_run_summary(
    task_type: TaskType,
    samples: list[dict],
    crash_count: int = 0,
    anr_count: int = 0,
    extra: Optional[dict] = None,
) -> dict:
    """Compute the summary JSON for a MobileSpecialRun.

    This function produces a RunSummary dict whose fields vary by task_type:
      - performance: avg/peak CPU, avg/peak memory, battery, crash/anr counts
      - stability: explore_duration, operation_interval, crash/anr counts,
                   completed_action_count, app_restart_count
      - fluency: avg_fps, total_jank_count, crash/anr counts

    Args:
        task_type: Type of the task (performance/stability/fluency)
        samples: List of metric samples from the run
        crash_count: Total crash incidents detected
        anr_count: Total ANR incidents detected
        extra: Additional task-type-specific fields

    Returns:
        dict suitable for MobileSpecialRun.summary_json
    """
    aggregated = aggregate_samples(samples)

    summary: dict[str, Any] = {
        "crash_count": crash_count,
        "anr_count": anr_count,
    }

    if task_type == TaskType.performance:
        summary.update(
            {
                "avg_cpu_pct": aggregated.get(MetricType.cpu_pct.value, {}).get("avg"),
                "peak_cpu_pct": aggregated.get(MetricType.cpu_pct.value, {}).get("max"),
                "avg_mem_mb": aggregated.get(MetricType.mem_mb.value, {}).get("avg"),
                "peak_mem_mb": aggregated.get(MetricType.mem_mb.value, {}).get("max"),
                "avg_battery_pct": aggregated.get(MetricType.battery_pct.value, {}).get("avg"),
            }
        )

    elif task_type == TaskType.stability:
        stability_extra = extra if isinstance(extra, dict) else {}
        summary.update(
            {
                "explore_duration_seconds": stability_extra.get("explore_duration_seconds"),
                "operation_interval_ms": stability_extra.get("operation_interval_ms"),
                "completed_action_count": stability_extra.get("completed_action_count", 0),
                "app_restart_count": stability_extra.get("app_restart_count", 0),
            }
        )

    elif task_type == TaskType.fluency:
        summary.update(
            {
                "avg_fps": aggregated.get(MetricType.fps.value, {}).get("avg"),
                "peak_fps": aggregated.get(MetricType.fps.value, {}).get("max"),
                "total_jank_count": aggregated.get(MetricType.jank_count.value, {}).get("max", 0),
            }
        )

    # Always include sample counts for debugging
    summary["_sample_counts"] = {mt: agg["count"] for mt, agg in aggregated.items()}

    return summary
