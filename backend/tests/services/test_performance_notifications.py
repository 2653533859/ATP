from app.services.performance_notifications import build_performance_notification_summary


def test_performance_notification_marks_threshold_failure():
    summary = build_performance_notification_summary(
        test_name="首页压测",
        run_id=8,
        status="success",
        duration_ms=1200,
        summary={"rps": 20, "p95_ms": 400},
        gate={"status": "failed"},
    )

    assert summary["status"] == "failed"
    assert summary["failed"] == 1
    assert summary["performance_event_reasons"] == ["threshold_failed"]


def test_performance_notification_reports_multiple_operational_signals():
    summary = build_performance_notification_summary(
        test_name="接口压测",
        run_id=9,
        status="success",
        duration_ms=None,
        summary={"error_rate": 0.2},
        gate={"status": "passed"},
        baseline_regression=True,
        node_issue=True,
        resource_issue=True,
    )

    assert summary["status"] == "failed"
    assert summary["performance_event_reasons"] == ["baseline_regression", "node_issue", "resource_issue"]
