"""`services/mobile_special/aggregator.py` 的行为缝（Q15-05）。

该模块此前 9% 覆盖：只有导入被执行过，聚合逻辑与三种任务类型的 summary 形状
一行都没跑过。它的输出直接落到 `MobileSpecialRun.summary_json`，前端报告页按这些
字段名取值，所以字段名与"无样本时给什么"是有契约意义的。
"""

from __future__ import annotations

from app.models.mobile_special import MetricType, TaskType
from app.services.mobile_special.aggregator import aggregate_samples, compute_run_summary


def _sample(metric_type: str, value) -> dict:
    return {"metric_type": metric_type, "metric_value": value}


def test_aggregate_groups_by_metric_type_and_rounds_to_two_decimals():
    samples = [
        _sample(MetricType.cpu_pct.value, 10),
        _sample(MetricType.cpu_pct.value, 21),
        _sample(MetricType.cpu_pct.value, 34),
        _sample(MetricType.mem_mb.value, 512.456),
    ]

    result = aggregate_samples(samples)

    assert result[MetricType.cpu_pct.value] == {"avg": 21.67, "max": 34.0, "min": 10.0, "count": 3}
    assert result[MetricType.mem_mb.value] == {"avg": 512.46, "max": 512.46, "min": 512.46, "count": 1}


def test_aggregate_skips_samples_without_metric_type_and_defaults_missing_values():
    samples = [
        _sample(MetricType.fps.value, 60),
        {"metric_value": 999},  # 无 metric_type，整条丢弃
        {"metric_type": MetricType.fps.value},  # 无 metric_value，按 0 计
    ]

    result = aggregate_samples(samples)

    assert set(result) == {MetricType.fps.value}
    assert result[MetricType.fps.value]["count"] == 2
    assert result[MetricType.fps.value]["min"] == 0.0


def test_aggregate_of_nothing_is_an_empty_mapping():
    assert aggregate_samples([]) == {}


def test_performance_summary_exposes_cpu_memory_and_battery():
    samples = [
        _sample(MetricType.cpu_pct.value, 12.5),
        _sample(MetricType.cpu_pct.value, 47.5),
        _sample(MetricType.mem_mb.value, 300),
        _sample(MetricType.mem_mb.value, 500),
        _sample(MetricType.battery_pct.value, 80),
    ]

    summary = compute_run_summary(TaskType.performance, samples, crash_count=2, anr_count=1)

    assert summary["crash_count"] == 2
    assert summary["anr_count"] == 1
    assert summary["avg_cpu_pct"] == 30.0
    assert summary["peak_cpu_pct"] == 47.5
    assert summary["avg_mem_mb"] == 400.0
    assert summary["peak_mem_mb"] == 500.0
    assert summary["avg_battery_pct"] == 80.0
    assert summary["_sample_counts"][MetricType.cpu_pct.value] == 2


def test_performance_summary_without_samples_yields_none_not_zero():
    """区分"没采到"与"采到 0"：报告页要能把前者显示为空而不是 0。"""
    summary = compute_run_summary(TaskType.performance, [])

    assert summary["avg_cpu_pct"] is None
    assert summary["peak_mem_mb"] is None
    assert summary["avg_battery_pct"] is None
    assert summary["_sample_counts"] == {}


def test_stability_summary_reads_its_fields_from_extra():
    summary = compute_run_summary(
        TaskType.stability,
        [_sample(MetricType.cpu_pct.value, 20)],
        crash_count=3,
        anr_count=4,
        extra={
            "explore_duration_seconds": 600,
            "operation_interval_ms": 800,
            "completed_action_count": 152,
            "app_restart_count": 2,
        },
    )

    assert summary["explore_duration_seconds"] == 600
    assert summary["operation_interval_ms"] == 800
    assert summary["completed_action_count"] == 152
    assert summary["app_restart_count"] == 2
    assert summary["crash_count"] == 3 and summary["anr_count"] == 4
    # 稳定性不产出 CPU 字段，但样本计数仍然保留供排查
    assert "avg_cpu_pct" not in summary
    assert summary["_sample_counts"][MetricType.cpu_pct.value] == 1


def test_stability_summary_tolerates_a_non_dict_extra():
    """extra 由调用方拼装，传成 None 或列表时不能把整个 summary 打崩。"""
    for bad_extra in (None, [], "oops"):
        summary = compute_run_summary(TaskType.stability, [], extra=bad_extra)

        assert summary["explore_duration_seconds"] is None
        assert summary["operation_interval_ms"] is None
        # 计数类字段有默认值 0
        assert summary["completed_action_count"] == 0
        assert summary["app_restart_count"] == 0


def test_fluency_summary_reports_fps_and_peak_jank():
    samples = [
        _sample(MetricType.fps.value, 58),
        _sample(MetricType.fps.value, 42),
        _sample(MetricType.jank_count.value, 3),
        _sample(MetricType.jank_count.value, 11),
    ]

    summary = compute_run_summary(TaskType.fluency, samples)

    assert summary["avg_fps"] == 50.0
    assert summary["peak_fps"] == 58.0
    # jank 是累计值，取最大即本次运行的总数
    assert summary["total_jank_count"] == 11.0


def test_fluency_summary_without_jank_samples_defaults_to_zero():
    summary = compute_run_summary(TaskType.fluency, [_sample(MetricType.fps.value, 60)])

    assert summary["avg_fps"] == 60.0
    assert summary["total_jank_count"] == 0, "没有 jank 样本时应为 0，而不是 None"
