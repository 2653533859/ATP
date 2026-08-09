"""Build performance-specific notification summaries."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any


def build_performance_notification_summary(
    *,
    test_name: str,
    run_id: int,
    status: str,
    duration_ms: int | None,
    summary: Mapping[str, Any] | None,
    gate: Mapping[str, Any] | None,
    baseline_regression: bool = False,
    node_issue: bool = False,
    resource_issue: bool = False,
) -> dict[str, Any]:
    """Map performance outcomes to the generic notification contract."""

    result_summary = dict(summary or {})
    gate_status = str((gate or {}).get("status") or "not_configured")
    failed = status != "success" or gate_status == "failed" or baseline_regression or node_issue or resource_issue
    event_reasons: list[str] = []
    if status != "success":
        event_reasons.append("run_failed")
    if gate_status == "failed":
        event_reasons.append("threshold_failed")
    if baseline_regression:
        event_reasons.append("baseline_regression")
    if node_issue:
        event_reasons.append("node_issue")
    if resource_issue:
        event_reasons.append("resource_issue")

    return {
        "title": f"性能压测 {test_name} Run #{run_id}",
        "status": "failed" if failed else "passed",
        "total": 1,
        "passed": 0 if failed else 1,
        "failed": 1 if failed else 0,
        "error": 0,
        "duration_ms": duration_ms or 0,
        "trigger_type": "manual",
        "entity_type": "performance",
        "performance_run_id": run_id,
        "performance_event_reasons": event_reasons,
        "threshold_status": gate_status,
        "rps": result_summary.get("rps"),
        "p95_ms": result_summary.get("p95_ms"),
        "p99_ms": result_summary.get("p99_ms"),
        "error_rate": result_summary.get("error_rate"),
    }
