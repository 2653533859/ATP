def test_incident_drill_covers_each_scheduled_plan_boundary(repo_file):
    content = repo_file("docs/scheduled-plan-incident-drill.md")

    for marker in (
        "check_cron_plans",
        "run_test_plan",
        "Redis DB 0",
        "Redis DB 1",
        "Redis DB 2",
        "plan_runs",
        "suite_runs",
        "test_runs",
        "notification_configs",
        "auto_bugs",
        "auto_bugs_error",
        "Celery, Redis, database, notification, and bug-tracker",
    ):
        assert marker in content


def test_incident_drill_documents_safe_recovery_invariants(repo_file):
    content = repo_file("docs/scheduled-plan-incident-drill.md")

    assert "PostgreSQL remains authoritative" in content
    assert "stale `running` rows have no automatic recovery" in content
    assert "Never call `run_test_plan.delay` manually against the same `PLAN_RUN_ID`" in content
    assert "Do not replay `run_test_plan` to repair bug creation" in content
    assert "Do not rerun the plan solely to resend a notification" in content
    assert "absent from Celery `active`, `reserved`, and `scheduled`" in content


def test_incident_drill_matches_worker_implementation_contract(repo_file):
    tasks = repo_file("backend/app/worker/tasks.py")
    celery = repo_file("backend/app/worker/celery_app.py")
    cleanup = repo_file("backend/app/worker/tasks_cleanup.py")
    notifier = repo_file("backend/app/services/notifier.py")

    assert '"check-cron-plans"' in celery
    assert '"task": "check_cron_plans"' in celery
    assert '"run_test_plan": {"queue": "default"}' in celery
    assert "trigger_type=TriggerType.cron" in tasks
    assert "enqueue_task(run_test_plan" in tasks
    assert '"auto_bugs": bug_results' in tasks
    assert '"auto_bugs_error": str(e)[:500]' in tasks
    assert "Plan notification failed" in tasks
    assert "PlanRun.status == PlanRunStatus.pending" in cleanup
    assert 'scope == "plans"' in notifier
    assert 'config.get("status_filters")' in notifier
