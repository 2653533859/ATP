"""Capacity-test analysis for ordered performance runs."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any


def analyze_capacity_runs(
    runs: Sequence[Mapping[str, Any]],
    *,
    max_error_rate: float = 0.01,
    max_p95_ms: float | None = None,
    min_stable_runs: int = 1,
) -> dict[str, Any]:
    """Identify the highest stable load and the first observed bottleneck.

    Runs are sorted by their declared VU/user/concurrency load. The function
    only treats successful runs inside the configured thresholds as stable;
    missing load or metrics remains visible as an explicit observation instead
    of being silently considered a pass.
    """

    if not 0 <= max_error_rate <= 1:
        raise ValueError("max_error_rate 必须在 0 到 1 之间")
    if max_p95_ms is not None and max_p95_ms < 0:
        raise ValueError("max_p95_ms 不能为负数")
    if min_stable_runs < 1:
        raise ValueError("min_stable_runs 必须大于 0")

    observations: list[dict[str, Any]] = []
    for run in runs:
        raw_summary = run.get("summary")
        summary: Mapping[str, Any] = raw_summary if isinstance(raw_summary, Mapping) else {}
        raw_options = run.get("options_snapshot")
        options: Mapping[str, Any] = raw_options if isinstance(raw_options, Mapping) else {}
        load = _load_value(options) or _number(summary.get("load"))
        error_rate = _number(summary.get("error_rate"))
        p95_ms = _number(summary.get("p95_ms"))
        reasons: list[str] = []
        if str(run.get("status")) != "success":
            reasons.append("run_not_success")
        if load is None:
            reasons.append("load_missing")
        if error_rate is None:
            reasons.append("error_rate_missing")
        elif error_rate > max_error_rate:
            reasons.append("error_rate_exceeded")
        if max_p95_ms is not None:
            if p95_ms is None:
                reasons.append("p95_missing")
            elif p95_ms > max_p95_ms:
                reasons.append("p95_exceeded")
        observations.append(
            {
                "run_id": run.get("id"),
                "load": load,
                "status": str(run.get("status")),
                "error_rate": error_rate,
                "p95_ms": p95_ms,
                "stable": not reasons,
                "reasons": reasons,
            }
        )

    observations.sort(key=lambda item: (item["load"] is None, item["load"] or 0, item["run_id"] or 0))
    stable = [item for item in observations if item["stable"]]
    result: dict[str, Any] = {
        "status": "ready" if len(stable) >= min_stable_runs else "insufficient_stable_runs",
        "max_stable_load": max((item["load"] for item in stable if item["load"] is not None), default=None),
        "max_stable_run_id": next(
            (item["run_id"] for item in reversed(stable) if item["load"] is not None),
            None,
        ),
        "stable_run_count": len(stable),
        "observed_run_count": len(observations),
        "bottleneck": None,
        "observations": observations,
    }
    unstable = [item for item in observations if not item["stable"] and item["load"] is not None]
    if unstable:
        first = unstable[0]
        result["first_unstable_load"] = first["load"]
        result["bottleneck"] = first["reasons"][0] if first["reasons"] else "unknown"
    else:
        result["first_unstable_load"] = None
    return result


def _load_value(options: Mapping[str, Any]) -> float | None:
    values = [_number(options.get(key)) for key in ("vus", "users", "concurrency")]
    raw_stages = options.get("stages")
    if isinstance(raw_stages, Sequence) and not isinstance(raw_stages, (str, bytes, bytearray)):
        values.extend(_number(stage.get("target")) for stage in raw_stages if isinstance(stage, Mapping))
    valid = [value for value in values if value is not None]
    return max(valid) if valid else None


def _number(value: Any) -> float | None:
    if isinstance(value, bool):
        return None
    try:
        return float(value) if value is not None else None
    except (TypeError, ValueError):
        return None
