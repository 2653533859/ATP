from pathlib import Path


def repo_path(path: str) -> Path:
    return Path(__file__).resolve().parents[2] / path


def test_dashboard_alert_task_registered_in_celery_beat():
    content = repo_path("app/worker/celery_app.py").read_text(encoding="utf-8")

    assert '"check-dashboard-alerts"' in content
    assert '"task": "check_dashboard_alerts"' in content
    assert '"schedule": 3600.0' in content


def test_dashboard_alert_task_calls_service():
    content = repo_path("app/worker/tasks.py").read_text(encoding="utf-8")

    assert '@celery_app.task(name="check_dashboard_alerts")' in content
    assert "evaluate_dashboard_alerts" in content
