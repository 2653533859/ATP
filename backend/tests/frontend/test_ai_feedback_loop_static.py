import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from tests._paths import repo_path


def test_run_detail_allows_adopt_reject_feedback():
    run_detail = repo_path("frontend/src/views/run/RunDetail.vue").read_text(encoding="utf-8")
    api = repo_path("frontend/src/api/index.ts").read_text(encoding="utf-8")
    backend = repo_path("backend/app/api/v1/cases/runs.py").read_text(encoding="utf-8")

    assert "onHealingFeedback(step, 'adopted')" in run_detail
    assert "onHealingFeedback(step, 'rejected')" in run_detail
    assert "submitHealingFeedback" in api
    assert '"/runs/{run_id}/steps/{step_id}/healing/feedback"' in backend
    assert "step.healing_feedback = body.action" in backend
    assert "step.healing_feedback_at = datetime.now(timezone.utc)" in backend


def test_feedback_is_aggregated_and_reported_with_effectiveness_metrics():
    aggregate = repo_path("backend/app/services/healing_feedback.py").read_text(encoding="utf-8")
    stats = repo_path("backend/app/services/ai_healing_stats.py").read_text(encoding="utf-8")
    stats_api = repo_path("backend/app/api/v1/ai_healing_stats.py").read_text(encoding="utf-8")
    task = repo_path("backend/app/worker/tasks_healing.py").read_text(encoding="utf-8")

    assert "def summarize_feedback_rows(" in aggregate
    assert "adopted_count" in aggregate
    assert "rejected_count" in aggregate
    assert "adopted_rate" in aggregate
    assert "async def aggregate_healing_feedback(" in aggregate
    assert "_is_ai_healing_regression" in stats
    assert "regression_success_rate" in stats
    assert '@router.get("/stats", response_model=AIHealingStatsOut)' in stats_api
    assert '@celery_app.task(name="aggregate_healing_feedback"' in task


def test_feedback_stats_page_is_reachable_from_system_routes():
    view = repo_path("frontend/src/views/system/AIHealingStatsView.vue").read_text(encoding="utf-8")
    router = repo_path("frontend/src/router/index.ts").read_text(encoding="utf-8")

    assert "总反馈数" in view
    assert "总采纳率" in view
    assert "回归通过率" in view
    assert "错误特征 Top 10" in view
    assert "system/ai-healing-stats" in router
    assert "AIHealingStatsView.vue" in router


def test_s5_04_is_marked_complete_in_roadmap():
    roadmap = repo_path("docs/optimization-roadmap-2026.md").read_text(encoding="utf-8")

    assert "| S5-04 | AI 诊断反馈闭环 | P2 | [x] 已完成 |" in roadmap
