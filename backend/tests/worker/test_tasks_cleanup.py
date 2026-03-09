import sys
import types
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))


def _import_tasks_cleanup(monkeypatch):
    class FakeCeleryApp:
        def task(self, *args, **kwargs):
            def decorator(func):
                return func

            return decorator

    monkeypatch.setitem(sys.modules, "app.worker.celery_app", types.SimpleNamespace(celery_app=FakeCeleryApp()))
    monkeypatch.setitem(
        sys.modules,
        "app.core.minio_client",
        types.SimpleNamespace(list_objects=lambda prefix: [], delete_file=lambda object_name: None),
    )
    sys.modules.pop("app.worker.tasks_cleanup", None)

    from app.worker import tasks_cleanup

    return tasks_cleanup


def test_cleanup_stale_pending_runs_skip_when_disabled(monkeypatch):
    tasks_cleanup = _import_tasks_cleanup(monkeypatch)
    monkeypatch.setattr(tasks_cleanup.settings, "STALE_PENDING_CLEANUP_ENABLED", False)

    session_factory_calls = 0

    def fake_session_factory():
        nonlocal session_factory_calls
        session_factory_calls += 1
        raise AssertionError("disabled 时不应创建数据库会话")

    monkeypatch.setitem(sys.modules, "app.core.database", types.SimpleNamespace(sync_session_factory=fake_session_factory))

    result = tasks_cleanup.cleanup_stale_pending_runs()

    assert result == {"test_runs": 0, "suite_runs": 0, "plan_runs": 0, "total": 0}
    assert session_factory_calls == 0


def test_cleanup_stale_pending_with_session_updates_all_run_tables(monkeypatch):
    tasks_cleanup = _import_tasks_cleanup(monkeypatch)
    monkeypatch.setattr(tasks_cleanup.settings, "STALE_PENDING_TIMEOUT_MINUTES", 120)

    rowcounts = iter([3, 1, 2])
    executed = []

    class FakeSession:
        def execute(self, stmt):
            executed.append(stmt)
            return types.SimpleNamespace(rowcount=next(rowcounts))

    result = tasks_cleanup._cleanup_stale_pending_with_session(
        FakeSession(),
        datetime(2026, 3, 9, 15, 0, tzinfo=timezone.utc),
    )

    assert result == {"test_runs": 3, "suite_runs": 1, "plan_runs": 2, "total": 6}
    assert len(executed) == 3


def test_cleanup_stale_pending_runs_commits_and_closes_session(monkeypatch):
    tasks_cleanup = _import_tasks_cleanup(monkeypatch)
    monkeypatch.setattr(tasks_cleanup.settings, "STALE_PENDING_CLEANUP_ENABLED", True)
    monkeypatch.setattr(tasks_cleanup, "load_all_models", lambda: None)

    class FakeSession:
        def __init__(self):
            self.committed = False
            self.closed = False
            self.rolled_back = False

        def commit(self):
            self.committed = True

        def rollback(self):
            self.rolled_back = True

        def close(self):
            self.closed = True

    session = FakeSession()
    monkeypatch.setitem(
        sys.modules,
        "app.core.database",
        types.SimpleNamespace(sync_session_factory=lambda: session),
    )
    monkeypatch.setattr(
        tasks_cleanup,
        "_cleanup_stale_pending_with_session",
        lambda current_session, now: {"test_runs": 1, "suite_runs": 0, "plan_runs": 1, "total": 2},
    )

    result = tasks_cleanup.cleanup_stale_pending_runs()

    assert result == {"test_runs": 1, "suite_runs": 0, "plan_runs": 1, "total": 2}
    assert session.committed is True
    assert session.rolled_back is False
    assert session.closed is True
