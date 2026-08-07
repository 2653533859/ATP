"""Report helpers shared by performance exports and the UI contract."""

from __future__ import annotations

from typing import Any


def build_threshold_rows(summary: dict[str, Any] | None) -> list[dict[str, Any]]:
    thresholds = summary.get("thresholds") if isinstance(summary, dict) else None
    if not isinstance(thresholds, dict):
        return []

    rows: list[dict[str, Any]] = []
    for metric, rules in thresholds.items():
        if not isinstance(rules, dict):
            continue
        for rule, result in rules.items():
            rows.append(
                {
                    "metric": str(metric),
                    "rule": str(rule),
                    "ok": _threshold_result_ok(result),
                }
            )
    return rows


def build_threshold_gate(summary: dict[str, Any] | None) -> dict[str, Any]:
    rows = build_threshold_rows(summary)
    passed = sum(1 for row in rows if row["ok"])
    failed = len(rows) - passed
    return {
        "status": "not_configured" if not rows else ("passed" if failed == 0 else "failed"),
        "total": len(rows),
        "passed": passed,
        "failed": failed,
    }


def build_performance_gate(status: str, summary: dict[str, Any] | None) -> dict[str, Any]:
    """Build the stable gate contract used by the UI and CI clients."""
    threshold_gate = build_threshold_gate(summary)
    if status in {"pending", "running", "cancelling"}:
        gate_status = "pending"
        ready = False
    elif status == "cancelled":
        gate_status = "cancelled"
        ready = True
    elif status != "success":
        gate_status = "failed"
        ready = True
    else:
        gate_status = threshold_gate["status"]
        ready = True
    return {
        "status": gate_status,
        "ready": ready,
        "run_status": status,
        "total": threshold_gate["total"],
        "passed": threshold_gate["passed"],
        "failed": threshold_gate["failed"],
    }


_BASELINE_METRICS: tuple[tuple[str, str], ...] = (
    ("rps", "higher"),
    ("p95_ms", "lower"),
    ("p99_ms", "lower"),
    ("error_rate", "lower"),
)


def build_baseline_comparison(
    baseline_run_id: int,
    run_id: int,
    baseline_summary: dict[str, Any] | None,
    current_summary: dict[str, Any] | None,
) -> dict[str, Any]:
    """Compare the core performance indicators against a persisted baseline."""
    baseline_summary = baseline_summary if isinstance(baseline_summary, dict) else {}
    current_summary = current_summary if isinstance(current_summary, dict) else {}
    metrics: list[dict[str, Any]] = []
    for metric, preferred_direction in _BASELINE_METRICS:
        baseline = _numeric_metric(baseline_summary.get(metric))
        current = _numeric_metric(current_summary.get(metric))
        delta = current - baseline if baseline is not None and current is not None else None
        delta_percent = (delta / abs(baseline) * 100) if delta is not None and baseline else None
        if delta is None or delta == 0:
            direction = "unknown" if delta is None else "unchanged"
        elif (preferred_direction == "higher" and delta > 0) or (preferred_direction == "lower" and delta < 0):
            direction = "improvement"
        else:
            direction = "regression"
        metrics.append(
            {
                "metric": metric,
                "preferred_direction": preferred_direction,
                "baseline": baseline,
                "current": current,
                "delta": delta,
                "delta_percent": delta_percent,
                "direction": direction,
            }
        )
    return {
        "baseline_run_id": baseline_run_id,
        "run_id": run_id,
        "metrics": metrics,
    }


def _threshold_result_ok(result: object) -> bool:
    if isinstance(result, bool):
        return not result
    if isinstance(result, dict):
        return result.get("ok") is True
    return False


def _numeric_metric(value: object) -> float | None:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    return float(value)
