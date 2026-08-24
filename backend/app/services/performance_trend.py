"""Daily trend aggregation for persisted performance runs."""

from __future__ import annotations

from collections.abc import Iterator, Mapping, Sequence
from datetime import date, datetime, timedelta, timezone
import math
from typing import Any

_METRICS = ("rps", "p95_ms", "p99_ms", "error_rate")
_ACTIVE_STATUSES = {"pending", "running", "cancelling"}


def build_performance_trend(
    runs: Sequence[Any],
    *,
    project_id: int,
    days: int = 30,
    now: datetime | None = None,
) -> dict[str, Any]:
    """Build a fixed-width daily trend from project-scoped run rows.

    ``days`` includes the current UTC calendar day. Sharded parent runs are
    excluded because their child runs represent the actual node executions.
    Metric values are arithmetic means of the run summaries that provide the
    metric; the API deliberately labels them as averages rather than merging
    percentile samples that are not available at this layer.
    """

    if not 1 <= days <= 365:
        raise ValueError("趋势天数必须在 1 到 365 之间")

    end_at = _as_utc(now or datetime.now(timezone.utc))
    end_date = end_at.date()
    start_date = end_date - timedelta(days=days - 1)
    start_at = datetime.combine(start_date, datetime.min.time(), tzinfo=timezone.utc)
    buckets = {item: _TrendBucket() for item in _date_range(start_date, end_date)}

    for run in runs:
        if _is_sharded_parent(run):
            continue
        captured_at = _run_timestamp(run)
        if captured_at is None or captured_at.date() not in buckets:
            continue
        buckets[captured_at.date()].add(_run_status(run), _run_summary(run))

    points = [bucket.to_dict(period) for period, bucket in buckets.items()]
    totals = _TrendBucket()
    for run in runs:
        if _is_sharded_parent(run):
            continue
        captured_at = _run_timestamp(run)
        if captured_at is None or captured_at.date() not in buckets:
            continue
        totals.add(_run_status(run), _run_summary(run))

    return {
        "project_id": project_id,
        "days": days,
        "from_at": start_at,
        "to_at": end_at,
        **totals.to_dict(include_period=False),
        "points": points,
    }


def _date_range(start: date, end: date) -> Iterator[date]:
    current = start
    while current <= end:
        yield current
        current += timedelta(days=1)


class _TrendBucket:
    def __init__(self) -> None:
        self.run_count = 0
        self.success_count = 0
        self.failed_count = 0
        self.cancelled_count = 0
        self.active_count = 0
        self.other_count = 0
        self._metrics: dict[str, list[float]] = {metric: [] for metric in _METRICS}

    def add(self, status: str, summary: Mapping[str, Any]) -> None:
        self.run_count += 1
        if status == "success":
            self.success_count += 1
        elif status == "failed":
            self.failed_count += 1
        elif status == "cancelled":
            self.cancelled_count += 1
        elif status in _ACTIVE_STATUSES:
            self.active_count += 1
        else:
            self.other_count += 1
        for metric in _METRICS:
            value = _number(summary.get(metric))
            if value is not None:
                self._metrics[metric].append(value)

    def to_dict(self, period: date | None = None, *, include_period: bool = True) -> dict[str, Any]:
        result: dict[str, Any] = {
            "run_count": self.run_count,
            "success_count": self.success_count,
            "failed_count": self.failed_count,
            "cancelled_count": self.cancelled_count,
            "active_count": self.active_count,
            "other_count": self.other_count,
            "avg_rps": _average(self._metrics["rps"]),
            "avg_p95_ms": _average(self._metrics["p95_ms"]),
            "avg_p99_ms": _average(self._metrics["p99_ms"]),
            "avg_error_rate": _average(self._metrics["error_rate"]),
            "max_p95_ms": max(self._metrics["p95_ms"], default=None),
        }
        if include_period:
            result["date"] = period
        return result


def _is_sharded_parent(run: Any) -> bool:
    summary = _run_summary(run)
    return _read(run, "parent_run_id") is None and summary.get("sharded") is True


def _run_summary(run: Any) -> Mapping[str, Any]:
    value = _read(run, "summary", {})
    return value if isinstance(value, Mapping) else {}


def _run_status(run: Any) -> str:
    value = _read(run, "status", "unknown")
    return str(getattr(value, "value", value))


def _run_timestamp(run: Any) -> datetime | None:
    for field in ("finished_at", "started_at", "created_at"):
        value = _read(run, field)
        if isinstance(value, datetime):
            return _as_utc(value)
    return None


def _read(item: Any, field: str, default: Any = None) -> Any:
    if isinstance(item, Mapping):
        return item.get(field, default)
    return getattr(item, field, default)


def _as_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def _number(value: Any) -> float | None:
    if isinstance(value, bool) or value is None:
        return None
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        return None
    return parsed if math.isfinite(parsed) else None


def _average(values: list[float]) -> float | None:
    return sum(values) / len(values) if values else None
