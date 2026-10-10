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
    # 窗口聚合已统一收敛到 flaky_detector 共享服务；CRUD 只负责委派。
    crud = repo_path("backend/app/api/v1/cases/crud.py").read_text(encoding="utf-8")
    assert "from app.services.flaky_detector import attach_flaky_stats" in crud
    assert "await attach_flaky_stats(db, cases)" in crud

    detector = repo_path("backend/app/services/flaky_detector.py").read_text(encoding="utf-8")
    assert "FLAKY_WINDOW_SIZE = 10" in detector
    assert "FLAKY_MIN_RUNS = 4" in detector
    assert "func.row_number()" in detector
    assert "TestRun.parent_run_id.is_(None)" in detector
    assert 'stats["passed_runs"] > 0' in detector
    assert "failure_runs > 0" in detector


def test_suite_worker_persists_flaky_flags_for_report_rows():
    # 任务层只负责接线 mark_flaky_fn；标记写入在共享编排服务中完成。
    tasks = repo_path("backend/app/worker/tasks.py").read_text(encoding="utf-8")
    assert "_mark_flaky_case_results" in tasks
    assert 'kwargs.setdefault("mark_flaky_fn", _mark_flaky_case_results)' in tasks

    orchestrator = repo_path("backend/app/services/suite_orchestrator.py").read_text(encoding="utf-8")
    assert 'result["flaky"]' in orchestrator
    assert 'result["flaky_failure_rate"]' in orchestrator
