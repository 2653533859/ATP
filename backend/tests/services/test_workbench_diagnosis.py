"""工作台跨执行类型规则诊断的确定性回归测试。"""

from app.services.workbench_diagnosis import build_rule_task_diagnosis


def test_android_diagnosis_prioritizes_anr_over_generic_incidents():
    result = build_rule_task_diagnosis(
        task_type="android",
        run_id=8,
        status="failed",
        task_name="Karing 稳定性",
        summary={"anr_count": 1, "crash_count": 0},
        incident_count=1,
    )

    assert "无响应" in result["summary"]
    assert result["repair_suggestions"][0]["target"] == "anr_trace_and_device_load"
    assert result["status"] == "done"


def test_android_diagnosis_exposes_event_errors_and_bounded_error_text():
    result = build_rule_task_diagnosis(
        task_type="android",
        run_id=9,
        status="stopped",
        summary={"error_message": "  device disconnected\n" + "x" * 500},
        event_error_count=2,
    )

    assert "event_error_count=2" in result["summary"]
    assert result["error_samples"][0]["error_message"].endswith("...(truncated)")


def test_performance_diagnosis_uses_latency_evidence_when_no_executor_error():
    result = build_rule_task_diagnosis(
        task_type="performance",
        run_id=10,
        status="failed",
        summary={"p95_ms": 830.5, "error_rate": 0},
    )

    assert "响应延迟" in result["summary"]
    assert "p95_ms=830.5" in result["summary"]
    assert result["repair_suggestions"][0]["target"] == "latency_threshold_and_baseline"


def test_suite_diagnosis_is_skipped_for_non_failed_run():
    result = build_rule_task_diagnosis(
        task_type="suite",
        run_id=11,
        status="passed",
        summary={"total": 3, "failed": 0, "error": 0},
    )

    assert result["status"] == "skipped"
    assert result["repair_suggestions"] == []
