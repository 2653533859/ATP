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


class _FakeSession:
    def __init__(self):
        self.closed = False
        self.rolled_back = False
        self.committed = False

    def rollback(self):
        self.rolled_back = True

    def close(self):
        self.closed = True

    def commit(self):
        self.committed = True


def test_cleanup_expired_files_iterates_active_policies(monkeypatch):
    tasks_cleanup = _import_tasks_cleanup(monkeypatch)
    monkeypatch.setattr(tasks_cleanup, "load_all_models", lambda: None)

    session = _FakeSession()
    monkeypatch.setitem(
        sys.modules,
        "app.core.database",
        types.SimpleNamespace(sync_session_factory=lambda: session),
    )

    from app.services.storage_cleanup import PolicyEntry

    policies = [
        PolicyEntry(prefix="screenshots/", retention_days=15),
        PolicyEntry(prefix="reports/", retention_days=60),
    ]
    monkeypatch.setattr(tasks_cleanup, "load_active_policies", lambda _: policies)

    preview_calls = []
    execute_calls = []

    def fake_preview(current_session, *, prefixes, retention_days):
        preview_calls.append({"prefixes": list(prefixes), "retention_days": retention_days})
        return types.SimpleNamespace(
            deletable_objects=[types.SimpleNamespace(object_name=f"{prefixes[0]}a.bin")]
        )

    def fake_execute(current_session, *, object_names, repair_orphan_references):
        execute_calls.append(
            {"object_names": list(object_names), "repair_orphan_references": repair_orphan_references}
        )
        return types.SimpleNamespace(deleted_count=1)

    monkeypatch.setattr(tasks_cleanup, "preview_storage_cleanup", fake_preview)
    monkeypatch.setattr(tasks_cleanup, "execute_storage_cleanup", fake_execute)

    result = tasks_cleanup.cleanup_expired_files()

    assert result == {"deleted": 2, "policies": 2}
    assert preview_calls == [
        {"prefixes": ["screenshots/"], "retention_days": 15},
        {"prefixes": ["reports/"], "retention_days": 60},
    ]
    assert all(item["repair_orphan_references"] for item in execute_calls)
    assert session.closed is True


def test_cleanup_expired_files_falls_back_to_defaults_when_no_policy(monkeypatch):
    tasks_cleanup = _import_tasks_cleanup(monkeypatch)
    monkeypatch.setattr(tasks_cleanup, "load_all_models", lambda: None)
    monkeypatch.setattr(tasks_cleanup.settings, "FILE_RETENTION_DAYS", 30)

    session = _FakeSession()
    monkeypatch.setitem(
        sys.modules,
        "app.core.database",
        types.SimpleNamespace(sync_session_factory=lambda: session),
    )
    monkeypatch.setattr(tasks_cleanup, "load_active_policies", lambda _: [])

    retentions = []

    def fake_preview(current_session, *, prefixes, retention_days):
        retentions.append((tuple(prefixes), retention_days))
        return types.SimpleNamespace(deletable_objects=[])

    monkeypatch.setattr(tasks_cleanup, "preview_storage_cleanup", fake_preview)

    result = tasks_cleanup.cleanup_expired_files()

    assert result == {"deleted": 0, "policies": len(tasks_cleanup.DEFAULT_CLEANUP_PREFIXES)}
    assert all(item[1] == 30 for item in retentions)
    assert {item[0][0] for item in retentions} == set(tasks_cleanup.DEFAULT_CLEANUP_PREFIXES)


def test_cleanup_stale_pending_runs_skip_when_disabled(monkeypatch):
    tasks_cleanup = _import_tasks_cleanup(monkeypatch)
    monkeypatch.setattr(tasks_cleanup.settings, "STALE_PENDING_CLEANUP_ENABLED", False)

    def fake_session_factory():
        raise AssertionError("disabled 时不应创建数据库会话")

    monkeypatch.setitem(sys.modules, "app.core.database", types.SimpleNamespace(sync_session_factory=fake_session_factory))

    result = tasks_cleanup.cleanup_stale_pending_runs()

    assert result == {"test_runs": 0, "suite_runs": 0, "plan_runs": 0, "total": 0}


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

    session = _FakeSession()
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


def test_cleanup_old_completed_runs_skip_when_disabled(monkeypatch):
    tasks_cleanup = _import_tasks_cleanup(monkeypatch)
    monkeypatch.setattr(tasks_cleanup.settings, "RUN_CLEANUP_ENABLED", False)

    def fake_session_factory():
        raise AssertionError("disabled 时不应创建数据库会话")

    monkeypatch.setitem(sys.modules, "app.core.database", types.SimpleNamespace(sync_session_factory=fake_session_factory))

    result = tasks_cleanup.cleanup_old_completed_runs()

    assert result == {"enabled": False}


def test_cleanup_old_completed_runs_invokes_cleaners_in_order(monkeypatch):
    tasks_cleanup = _import_tasks_cleanup(monkeypatch)
    monkeypatch.setattr(tasks_cleanup.settings, "RUN_CLEANUP_ENABLED", True)
    monkeypatch.setattr(tasks_cleanup.settings, "RUN_RETENTION_DAYS", 7)
    monkeypatch.setattr(tasks_cleanup.settings, "RUN_CLEANUP_BATCH_SIZE", 200)
    monkeypatch.setattr(tasks_cleanup, "load_all_models", lambda: None)

    session = _FakeSession()
    monkeypatch.setitem(
        sys.modules,
        "app.core.database",
        types.SimpleNamespace(sync_session_factory=lambda: session),
    )

    call_log: list[tuple[str, int]] = []
    simple_results = iter([5, 3])

    def fake_simple(current_session, model, status_field, statuses, cutoff, batch_size):
        name = model.__name__
        call_log.append((name, batch_size))
        return next(simple_results)

    def fake_test(current_session, cutoff, batch_size):
        call_log.append(("TestRun", batch_size))
        return {"runs": 9, "objects": 4}

    def fake_mobile(current_session, cutoff, batch_size):
        call_log.append(("MobileSpecialRun", batch_size))
        return {"runs": 2, "objects": 1}

    monkeypatch.setattr(tasks_cleanup, "_cleanup_simple_runs", fake_simple)
    monkeypatch.setattr(tasks_cleanup, "_cleanup_test_runs", fake_test)
    monkeypatch.setattr(tasks_cleanup, "_cleanup_mobile_special_runs", fake_mobile)

    result = tasks_cleanup.cleanup_old_completed_runs()

    assert result == {
        "plan_runs": 5,
        "suite_runs": 3,
        "test_runs": 9,
        "mobile_runs": 2,
        "deleted_objects": 5,
        "retention_days": 7,
    }
    assert [item[0] for item in call_log] == ["PlanRun", "SuiteRun", "TestRun", "MobileSpecialRun"]
    assert all(item[1] == 200 for item in call_log)
    assert session.closed is True


def test_cleanup_test_runs_collects_screenshots_then_deletes_rows(monkeypatch):
    tasks_cleanup = _import_tasks_cleanup(monkeypatch)

    collected_for: list[list[int]] = []
    deleted_objects: list[list[str]] = []

    def fake_collect(_session, ids):
        collected_for.append(list(ids))
        return [f"screenshots/{i}.png" for i in ids]

    def fake_delete(names):
        deleted_objects.append(list(names))
        return len(names)

    monkeypatch.setattr(tasks_cleanup, "_collect_screenshot_objects", fake_collect)
    monkeypatch.setattr(tasks_cleanup, "_delete_minio_objects", fake_delete)

    id_batches = iter([[1, 2, 3], []])
    commits = {"count": 0}
    delete_invocations: list[str] = []

    class StubSession:
        def execute(self, stmt):
            cls = stmt.__class__.__name__
            if cls.endswith("Select"):
                batch = next(id_batches)
                return types.SimpleNamespace(all=lambda batch=batch: [(value,) for value in batch])
            if cls.endswith("Delete"):
                delete_invocations.append(cls)
                return types.SimpleNamespace(all=lambda: [])
            raise AssertionError(f"unexpected stmt: {cls}")

        def commit(self):
            commits["count"] += 1

    stats = tasks_cleanup._cleanup_test_runs(StubSession(), datetime(2026, 1, 1, tzinfo=timezone.utc), batch_size=500)

    assert stats == {"runs": 3, "objects": 3}
    assert collected_for == [[1, 2, 3]]
    assert deleted_objects == [["screenshots/1.png", "screenshots/2.png", "screenshots/3.png"]]
    assert delete_invocations  # at least one delete executed
    assert commits["count"] == 1
