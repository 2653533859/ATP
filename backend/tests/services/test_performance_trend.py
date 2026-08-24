from datetime import datetime, timezone

import pytest

from app.services.performance_trend import build_performance_trend


def _run(run_id: int, created_at: datetime, *, status: str = "success", summary=None, parent_run_id=None):
    return {
        "id": run_id,
        "created_at": created_at,
        "status": status,
        "summary": summary or {},
        "parent_run_id": parent_run_id,
    }


def test_trend_keeps_empty_days_and_aggregates_leaf_runs():
    now = datetime(2026, 8, 24, 12, 0, tzinfo=timezone.utc)
    result = build_performance_trend(
        [
            _run(1, datetime(2026, 8, 24, 9, tzinfo=timezone.utc), summary={"rps": 10, "p95_ms": 100}),
            _run(2, datetime(2026, 8, 23, 9, tzinfo=timezone.utc), status="failed", summary={"p95_ms": 200}),
            _run(3, datetime(2026, 8, 22, 9, tzinfo=timezone.utc), status="running"),
            _run(4, datetime(2026, 8, 24, 10, tzinfo=timezone.utc), summary={"sharded": True}),
            _run(5, datetime(2026, 8, 24, 10, tzinfo=timezone.utc), parent_run_id=4, summary={"rps": 30, "p95_ms": 80}),
        ],
        project_id=7,
        days=4,
        now=now,
    )

    assert result["project_id"] == 7
    assert result["run_count"] == 4
    assert result["success_count"] == 2
    assert result["failed_count"] == 1
    assert result["active_count"] == 1
    assert [point["date"].isoformat() for point in result["points"]] == [
        "2026-08-21",
        "2026-08-22",
        "2026-08-23",
        "2026-08-24",
    ]
    assert result["points"][1]["active_count"] == 1
    assert result["points"][3]["avg_rps"] == 20
    assert result["points"][3]["max_p95_ms"] == 100


def test_trend_uses_finished_time_and_ignores_invalid_metrics():
    now = datetime(2026, 8, 24, 1, 0, tzinfo=timezone.utc)
    result = build_performance_trend(
        [
            {
                "id": 1,
                "created_at": datetime(2026, 8, 23, 23, tzinfo=timezone.utc),
                "finished_at": datetime(2026, 8, 24, 0, 30, tzinfo=timezone.utc),
                "status": "success",
                "summary": {"rps": "not-a-number", "error_rate": float("nan")},
            }
        ],
        project_id=7,
        days=1,
        now=now,
    )

    assert result["points"][0]["date"].isoformat() == "2026-08-24"
    assert result["points"][0]["run_count"] == 1
    assert result["points"][0]["avg_rps"] is None
    assert result["points"][0]["avg_error_rate"] is None


@pytest.mark.parametrize("days", [0, 366])
def test_trend_rejects_an_unbounded_window(days):
    with pytest.raises(ValueError, match="1 到 365"):
        build_performance_trend([], project_id=1, days=days)
