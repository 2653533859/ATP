"""Unit tests for D4.3 DORA Metrics Calculator Service."""

import pytest

from app.services.dora_metrics_calculator import (
    DoraLevel,
    compute_dora_metrics,
    get_dora_report,
    list_dora_reports,
    reset_dora_registry,
)


@pytest.fixture(autouse=True)
def clean_registry():
    reset_dora_registry()
    yield
    reset_dora_registry()


def test_compute_dora_metrics_elite():
    report = compute_dora_metrics(
        project_id=1,
        evaluation_period_days=30,
        total_deployments_count=60,  # 2.0 次/天 -> ELITE
        lead_time_for_changes_hours=0.5,  # 0.5h -> ELITE
        change_failure_rate_pct=2.0,  # 2.0% -> ELITE
        time_to_restore_service_minutes=25.0,  # 25min -> ELITE
        test_runs_on_time_count=98,
        test_runs_total_count=100,
    )

    assert report.overall_maturity_level == DoraLevel.ELITE
    assert report.test_on_time_completion_rate_pct == 98.0

    dims = report.dimensions
    assert dims["deployment_frequency"].level == DoraLevel.ELITE
    assert dims["lead_time_for_changes"].level == DoraLevel.ELITE
    assert dims["change_failure_rate"].level == DoraLevel.ELITE
    assert dims["time_to_restore_service"].level == DoraLevel.ELITE

    assert "Elite 卓越效能阶段" in report.engineering_efficiency_recommendations[0]


def test_compute_dora_metrics_medium_and_bottlenecks():
    report = compute_dora_metrics(
        project_id=2,
        evaluation_period_days=30,
        total_deployments_count=2,  # 2/30 = 0.067 -> MEDIUM
        lead_time_for_changes_hours=48.0,  # 48h -> MEDIUM
        change_failure_rate_pct=22.0,  # 22% -> MEDIUM
        time_to_restore_service_minutes=2880.0,  # 2天 -> MEDIUM
        test_runs_on_time_count=70,
        test_runs_total_count=100,
    )

    assert report.overall_maturity_level == DoraLevel.MEDIUM
    assert report.test_on_time_completion_rate_pct == 70.0

    # 验证瓶颈诊断提取
    bottlenecks_text = " ".join(report.bottlenecks_identified)
    assert "部署交付频次偏低" in bottlenecks_text
    assert "代码变更前置耗时过长" in bottlenecks_text
    assert "变更失败率偏高" in bottlenecks_text
    assert "故障平均恢复时长偏慢" in bottlenecks_text


def test_dora_report_lookup_and_reset():
    report = compute_dora_metrics(project_id=10)
    assert report.report_id.startswith("dora_rep_")

    fetched = get_dora_report(report.report_id)
    assert fetched is not None
    assert fetched.project_id == 10

    # 按项目查询
    p10_reports = list_dora_reports(project_id=10)
    assert len(p10_reports) == 1

    p99_reports = list_dora_reports(project_id=99)
    assert len(p99_reports) == 0
