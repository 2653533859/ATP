import sys
import types
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))


def _import_tasks(monkeypatch):
    class FakeCeleryApp:
        def task(self, *args, **kwargs):
            def decorator(func):
                return func

            return decorator

    monkeypatch.setitem(sys.modules, "app.worker.celery_app", types.SimpleNamespace(celery_app=FakeCeleryApp()))
    monkeypatch.setitem(sys.modules, "app.worker.case_dispatch", types.SimpleNamespace(dispatch_case=None))
    monkeypatch.setitem(sys.modules, "app.models.bootstrap", types.SimpleNamespace(load_all_models=lambda: None))
    monkeypatch.setitem(
        sys.modules,
        "app.core.redis_client",
        types.SimpleNamespace(
            publish_run_event=None,
            delete_json_cache_pattern=None,
        ),
    )
    monkeypatch.setitem(
        sys.modules, "app.core.encryption", types.SimpleNamespace(decrypt_env_vars=lambda values: values)
    )
    monkeypatch.setitem(sys.modules, "app.worker.async_runner", types.SimpleNamespace(run_async=lambda coro: None))
    sys.modules.pop("app.worker.tasks", None)

    from app.worker import tasks

    return tasks


def test_tasks_module_includes_stats_cache_invalidation_helper_call():
    tasks_file = Path(__file__).resolve().parents[2] / "app" / "worker" / "tasks.py"
    content = tasks_file.read_text(encoding="utf-8")

    assert "delete_json_cache_pattern" in content
    assert '"atp:stats:*"' in content
