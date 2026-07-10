import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from tests._paths import repo_path


def test_case_list_shows_flaky_stability_column():
    content = repo_path("frontend/src/views/case/CaseList.vue").read_text(encoding="utf-8")

    assert "case.stats.flaky_cases" in content
    assert "case.columns.stability" in content
    assert "record.flaky_stats?.is_flaky" in content
    assert "flakyTooltip(asCase(record))" in content
    assert "flakyCaseCount" in content


def test_suite_report_marks_flaky_case_results():
    content = repo_path("frontend/src/views/suite/SuiteList.vue").read_text(encoding="utf-8")

    assert "suite.case_columns.stability" in content
    assert "caseRun.flaky" in content
    assert "suite.report.flaky_case" in content


def test_flaky_i18n_keys_exist():
    zh = repo_path("frontend/src/locales/zh-CN.ts").read_text(encoding="utf-8")
    en = repo_path("frontend/src/locales/en-US.ts").read_text(encoding="utf-8")

    for content in (zh, en):
        assert "flaky_cases" in content
        assert "stability" in content
        assert "flaky: {" in content
        assert "flaky_case" in content
