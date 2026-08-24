from app.services.performance_report import (
    apply_baseline_gate,
    build_baseline_comparison,
    build_performance_gate,
)


def test_build_baseline_comparison_marks_metric_direction_by_business_meaning():
    result = build_baseline_comparison(
        baseline_run_id=1,
        run_id=2,
        baseline_summary={"rps": 100, "p95_ms": 100, "p99_ms": 200, "error_rate": 0.01},
        current_summary={"rps": 110, "p95_ms": 90, "p99_ms": 250, "error_rate": 0.02},
    )

    assert {row["metric"]: row["direction"] for row in result["metrics"]} == {
        "rps": "improvement",
        "p95_ms": "improvement",
        "p99_ms": "regression",
        "error_rate": "regression",
    }
    assert result["metrics"][0]["delta_percent"] == 10.0


def test_build_performance_gate_waits_for_terminal_run_and_requires_thresholds():
    assert build_performance_gate("running", {}) == {
        "status": "pending",
        "ready": False,
        "run_status": "running",
        "total": 0,
        "passed": 0,
        "failed": 0,
    }
    assert build_performance_gate("success", {})["status"] == "not_configured"
    assert (
        build_performance_gate(
            "success",
            {"thresholds": {"http_req_failed": {"rate<0.01": {"ok": True}}}},
        )["status"]
        == "passed"
    )
    assert build_performance_gate("failed", {})["status"] == "failed"


def test_apply_baseline_gate_can_require_a_baseline_or_fail_on_regression():
    base_gate = build_performance_gate("success", {"thresholds": {"rps": {">90": {"ok": True}}}})
    assert (
        apply_baseline_gate(
            base_gate,
            run_id=2,
            baseline_run_id=None,
            baseline_available=False,
            baseline_summary=None,
            current_summary={"rps": 100},
            require_baseline=True,
        )["status"]
        == "not_configured"
    )

    result = apply_baseline_gate(
        base_gate,
        run_id=2,
        baseline_run_id=1,
        baseline_available=True,
        baseline_summary={"rps": 100, "p95_ms": 100},
        current_summary={"rps": 90, "p95_ms": 120},
        fail_on_baseline_regression=True,
    )
    assert result["status"] == "failed"

    failed_run = apply_baseline_gate(
        build_performance_gate("failed", {}),
        run_id=3,
        baseline_run_id=None,
        baseline_available=False,
        baseline_summary=None,
        current_summary={},
        require_baseline=True,
    )
    assert failed_run["status"] == "failed"
