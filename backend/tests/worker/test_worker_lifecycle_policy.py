from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]


def _read(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def test_worker_lifecycle_doc_covers_state_retry_timeout_recovery_and_cancel():
    content = _read("docs/worker-lifecycle.md")

    assert "State Model" in content
    assert "Retry Policy" in content
    assert "Timeout Policy" in content
    assert "Recovery Policy" in content
    assert "Cancellation Policy" in content
    assert "`pending`" in content
    assert "`running`" in content
    assert "`passed`" in content
    assert "`failed`" in content
    assert "`error`" in content
    assert "`skipped`" in content


def test_celery_defaults_enforce_timeout_and_prefetch_policy():
    content = _read("backend/app/worker/celery_app.py")

    assert "task_track_started=True" in content
    assert "worker_prefetch_multiplier=1" in content
    assert "task_soft_time_limit=1500" in content
    assert "task_time_limit=1800" in content
    assert "worker_max_tasks_per_child=50" in content
    assert "cleanup_stale_pending_runs" in content


def test_primary_execution_tasks_do_not_auto_retry():
    content = _read("backend/app/worker/tasks.py")

    assert '@celery_app.task(bind=True, name="run_test_case")' in content
    assert '@celery_app.task(bind=True, name="run_test_suite")' in content
    assert '@celery_app.task(bind=True, name="run_test_plan")' in content
    for task_name in ("run_test_case", "run_test_suite", "run_test_plan"):
        task_line = next(line for line in content.splitlines() if f'name="{task_name}"' in line)
        assert "max_retries" not in task_line
        assert "autoretry_for" not in task_line


def test_retryable_maintenance_tasks_are_explicit():
    backup_content = _read("backend/app/worker/tasks_db_backup.py")
    healing_content = _read("backend/app/worker/tasks_healing.py")

    assert 'name="backup_postgres_daily", bind=True, max_retries=2, default_retry_delay=300' in backup_content
    assert 'name="backup_postgres_weekly", bind=True, max_retries=2, default_retry_delay=300' in backup_content
    assert 'name="aggregate_healing_feedback", bind=True, max_retries=1, default_retry_delay=300' in healing_content
    assert 'name="diagnose_step_failure", bind=True, max_retries=0, acks_late=True' in healing_content
    assert 'name="diagnose_run_failure", bind=True, max_retries=0, acks_late=True' in healing_content


def test_queue_doc_links_worker_lifecycle_policy():
    content = _read("docs/celery-queues.md")

    assert "worker-lifecycle.md" in content
