import ast
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]


def _task_routes() -> dict:
    tree = ast.parse((ROOT / "backend" / "app" / "worker" / "celery_app.py").read_text(encoding="utf-8"))
    for node in ast.walk(tree):
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute) and node.func.attr == "update":
            for keyword in node.keywords:
                if keyword.arg == "task_routes":
                    return ast.literal_eval(keyword.value)
    raise AssertionError("task_routes not found")


def _conf_keyword(name: str):
    tree = ast.parse((ROOT / "backend" / "app" / "worker" / "celery_app.py").read_text(encoding="utf-8"))
    for node in ast.walk(tree):
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute) and node.func.attr == "update":
            for keyword in node.keywords:
                if keyword.arg == name:
                    return ast.literal_eval(keyword.value)
    raise AssertionError(f"{name} not found")


def test_celery_task_routes_split_operational_queues():
    routes = _task_routes()

    assert routes["run_test_case"]["queue"] == "default"
    assert routes["run_mobile_special_task"]["queue"] == "mobile_special"
    assert routes["diagnose_step_failure"]["queue"] == "ai"
    assert routes["run_performance_test"]["queue"] == "performance"
    assert routes["check_performance_schedules"]["queue"] == "performance"
    assert routes["heartbeat_performance_node"]["queue"] == "performance"
    assert routes["heartbeat_android_worker"]["queue"] == "mobile_special"
    assert routes["cleanup_expired_files"]["queue"] == "maintenance"
    assert routes["cleanup_old_audit_logs"]["queue"] == "maintenance"
    assert routes["backup_postgres_daily"]["queue"] == "maintenance"


def test_performance_task_is_included_by_worker():
    tree = ast.parse((ROOT / "backend" / "app" / "worker" / "celery_app.py").read_text(encoding="utf-8"))
    for node in ast.walk(tree):
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id == "Celery":
            for keyword in node.keywords:
                if keyword.arg == "include":
                    includes = ast.literal_eval(keyword.value)
                    assert "app.worker.tasks_performance" in includes
                    return
    raise AssertionError("Celery include not found")


def test_default_queue_remains_default():
    assert _conf_keyword("task_default_queue") == "default"
    assert _conf_keyword("task_create_missing_queues") is True
