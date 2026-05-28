from pathlib import Path


def repo_path(path: str) -> Path:
    return Path(__file__).resolve().parents[2] / path


def test_healing_feedback_aggregate_task_registered_in_celery_beat():
    content = repo_path("app/worker/celery_app.py").read_text(encoding="utf-8")

    assert '"aggregate-healing-feedback"' in content
    assert '"task": "aggregate_healing_feedback"' in content
    assert "crontab(hour=4, minute=17, day_of_week=1)" in content


def test_healing_feedback_aggregate_task_calls_service():
    content = repo_path("app/worker/tasks_healing.py").read_text(encoding="utf-8")

    assert '@celery_app.task(name="aggregate_healing_feedback"' in content
    assert "from app.services.healing_feedback import aggregate_healing_feedback" in content
    assert "return await aggregate_healing_feedback(db)" in content
