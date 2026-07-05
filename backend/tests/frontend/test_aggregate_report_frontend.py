import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from tests._paths import repo_path


def test_suite_runs_show_aggregate_report_panel():
    content = repo_path("frontend/src/views/suite/SuiteList.vue").read_text(encoding="utf-8")

    assert "suite.report.title" in content
    assert "getSuiteRunPassRate" in content
    assert "getSuiteRunFailureItems(record).slice(0, 5)" in content
    assert "suite.report.case_details" in content
    assert "formatDuration(record.duration_ms)" in content


def test_plan_runs_show_aggregate_report_panel():
    content = repo_path("frontend/src/views/plan/PlanList.vue").read_text(encoding="utf-8")

    assert "plan.report.title" in content
    assert "getPlanRunPassRate" in content
    assert "getPlanRunFailureItems(record).slice(0, 5)" in content
    assert "plan.report.suite_details" in content
    assert "planRunSuiteColumns" in content


def test_shared_aggregate_report_styles_are_responsive():
    content = repo_path("frontend/src/styles/page-shell.css").read_text(encoding="utf-8")

    assert ".aggregate-report-panel" in content
    assert ".aggregate-report-grid" in content
    assert ".aggregate-report-value.danger" in content
    assert "@media (max-width: 480px)" in content
