import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from tests._paths import repo_path


def test_case_schema_exposes_flaky_stats():
    content = repo_path("backend/app/schemas/case.py").read_text(encoding="utf-8")

    assert "class CaseFlakyStats" in content
    assert "is_flaky: bool" in content
    assert "failure_rate: float" in content
    assert "flaky_stats: CaseFlakyStats" in content


def test_case_crud_computes_flaky_from_recent_terminal_runs():
    content = repo_path("backend/app/api/v1/cases/crud.py").read_text(encoding="utf-8")

    assert "FLAKY_WINDOW_SIZE = 10" in content
    assert "FLAKY_MIN_RUNS = 4" in content
    assert "func.row_number()" in content
    assert "TestRun.parent_run_id.is_(None)" in content
    assert "stats[\"passed_runs\"] > 0" in content
    assert "failure_runs > 0" in content


def test_suite_worker_persists_flaky_flags_for_report_rows():
    content = repo_path("backend/app/worker/tasks.py").read_text(encoding="utf-8")

    assert "_mark_flaky_case_results" in content
    assert "result[\"flaky\"]" in content
    assert "result[\"flaky_failure_rate\"]" in content
    assert "await _mark_flaky_case_results(db, case_run_results)" in content
