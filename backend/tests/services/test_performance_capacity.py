import pytest

from app.services.performance_capacity import analyze_capacity_runs


def test_capacity_analysis_finds_highest_stable_load_and_bottleneck():
    result = analyze_capacity_runs(
        [
            {
                "id": 2,
                "status": "success",
                "options_snapshot": {"vus": 20},
                "summary": {"error_rate": 0.0, "p95_ms": 80},
            },
            {
                "id": 3,
                "status": "success",
                "options_snapshot": {"vus": 40},
                "summary": {"error_rate": 0.02, "p95_ms": 90},
            },
            {
                "id": 1,
                "status": "success",
                "options_snapshot": {"vus": 10},
                "summary": {"error_rate": 0.0, "p95_ms": 60},
            },
        ],
        max_error_rate=0.01,
        max_p95_ms=100,
    )

    assert result["status"] == "ready"
    assert result["max_stable_load"] == 20
    assert result["max_stable_run_id"] == 2
    assert result["first_unstable_load"] == 40
    assert result["bottleneck"] == "error_rate_exceeded"


def test_capacity_analysis_does_not_treat_missing_metrics_as_stable():
    result = analyze_capacity_runs(
        [{"id": 1, "status": "success", "options_snapshot": {"concurrency": 5}, "summary": {}}]
    )

    assert result["status"] == "insufficient_stable_runs"
    assert result["observations"][0]["reasons"] == ["error_rate_missing"]


@pytest.mark.parametrize("kwargs", [{"max_error_rate": -0.1}, {"max_p95_ms": -1}, {"min_stable_runs": 0}])
def test_capacity_analysis_validates_thresholds(kwargs):
    with pytest.raises(ValueError):
        analyze_capacity_runs([], **kwargs)
