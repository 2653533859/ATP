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
        self.executed = []
        self.added = []

    def rollback(self):
        self.rolled_back = True

    def close(self):
        self.closed = True

    def commit(self):
        self.committed = True

    def execute(self, statement):
        self.executed.append(statement)
        return types.SimpleNamespace(rowcount=7)

    def add(self, obj):
        self.added.append(obj)


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
        PolicyEntry(prefix="screenshots/", retention_days=15, max_size_gb=None),
        PolicyEntry(prefix="reports/", retention_days=60, max_size_gb=2.0),
    ]
    monkeypatch.setattr(tasks_cleanup, "load_active_policies", lambda _: policies)

    preview_calls = []
    execute_calls = []

    def fake_preview(current_session, *, policies):
        policy = policies[0]
        preview_calls.append(
            {
                "prefix": policy.prefix,
                "retention_days": policy.retention_days,
                "max_size_gb": policy.max_size_gb,
            }
        )
        return types.SimpleNamespace(
            deletable_objects=[types.SimpleNamespace(object_name=f"{policy.prefix}a.bin")],
            size_evicted_count=1 if policy.max_size_gb else 0,
        )

    def fake_execute(current_session, *, object_names, prefixes, repair_orphan_references):
        execute_calls.append(
            {
                "object_names": list(object_names),
                "prefixes": list(prefixes),
                "repair_orphan_references": repair_orphan_references,
            }
        )
        return types.SimpleNamespace(deleted_count=1)

    monkeypatch.setattr(tasks_cleanup, "preview_storage_cleanup", fake_preview)
    monkeypatch.setattr(tasks_cleanup, "execute_storage_cleanup", fake_execute)

    result = tasks_cleanup.cleanup_expired_files()

    assert result == {"deleted": 2, "size_evicted": 1, "policies": 2}
    assert preview_calls == [
        {"prefix": "screenshots/", "retention_days": 15, "max_size_gb": None},
        {"prefix": "reports/", "retention_days": 60, "max_size_gb": 2.0},
    ]
    assert all(item["repair_orphan_references"] for item in execute_calls)
    assert [item["prefixes"] for item in execute_calls] == [["screenshots/"], ["reports/"]]
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

    fallback_prefixes = []

    def fake_preview(current_session, *, policies):
        policy = policies[0]
        fallback_prefixes.append(policy.prefix)
        assert policy.retention_days == 30
        assert policy.max_size_gb is None
        return types.SimpleNamespace(deletable_objects=[], size_evicted_count=0)

    monkeypatch.setattr(tasks_cleanup, "preview_storage_cleanup", fake_preview)

    result = tasks_cleanup.cleanup_expired_files()

    assert result == {
        "deleted": 0,
        "size_evicted": 0,
        "policies": len(tasks_cleanup.DEFAULT_CLEANUP_PREFIXES),
    }
    assert set(fallback_prefixes) == set(tasks_cleanup.DEFAULT_CLEANUP_PREFIXES)


def test_cleanup_stale_pending_runs_skip_when_disabled(monkeypatch):
    tasks_cleanup = _import_tasks_cleanup(monkeypatch)
    monkeypatch.setattr(tasks_cleanup.settings, "STALE_PENDING_CLEANUP_ENABLED", False)

    def fake_session_factory():
        raise AssertionError("disabled 时不应创建数据库会话")

    monkeypatch.setitem(
        sys.modules, "app.core.database", types.SimpleNamespace(sync_session_factory=fake_session_factory)
    )

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

    monkeypatch.setitem(
        sys.modules, "app.core.database", types.SimpleNamespace(sync_session_factory=fake_session_factory)
    )

    result = tasks_cleanup.cleanup_old_completed_runs()

    assert result == {"enabled": False}


def test_cleanup_old_notification_deliveries_skip_when_disabled(monkeypatch):
    tasks_cleanup = _import_tasks_cleanup(monkeypatch)
    monkeypatch.setattr(tasks_cleanup.settings, "NOTIFICATION_DELIVERY_CLEANUP_ENABLED", False)

    def fake_session_factory():
        raise AssertionError("disabled 时不应创建数据库会话")

    monkeypatch.setitem(
        sys.modules,
        "app.core.database",
        types.SimpleNamespace(sync_session_factory=fake_session_factory),
    )

    result = tasks_cleanup.cleanup_old_notification_deliveries()

    assert result == {"enabled": False, "deleted": 0, "retention_days": 30}


def test_cleanup_old_notification_deliveries_deletes_before_cutoff(monkeypatch):
    tasks_cleanup = _import_tasks_cleanup(monkeypatch)
    monkeypatch.setattr(tasks_cleanup.settings, "NOTIFICATION_DELIVERY_CLEANUP_ENABLED", True)
    monkeypatch.setattr(tasks_cleanup.settings, "NOTIFICATION_DELIVERY_RETENTION_DAYS", 14)

    session = _FakeSession()
    monkeypatch.setitem(
        sys.modules,
        "app.core.database",
        types.SimpleNamespace(sync_session_factory=lambda: session),
    )

    result = tasks_cleanup.cleanup_old_notification_deliveries()

    assert result == {"enabled": True, "deleted": 7, "retention_days": 14}
    assert len(session.executed) == 1
    assert len(session.added) == 1
    assert session.added[0].action == "notification_delivery_cleanup"
    assert session.added[0].resource_type == "notification_delivery"
    assert "14 days" in session.added[0].detail
    assert session.committed is True
    assert session.closed is True


def test_cleanup_old_audit_logs_skip_when_disabled(monkeypatch):
    tasks_cleanup = _import_tasks_cleanup(monkeypatch)
    monkeypatch.setattr(tasks_cleanup.settings, "AUDIT_LOG_CLEANUP_ENABLED", False)

    def fake_session_factory():
        raise AssertionError("审计日志清理关闭时不应创建数据库会话")

    monkeypatch.setitem(
        sys.modules,
        "app.core.database",
        types.SimpleNamespace(sync_session_factory=fake_session_factory),
    )

    result = tasks_cleanup.cleanup_old_audit_logs()

    assert result == {"enabled": False, "deleted": 0, "retention_days": 365}


def test_cleanup_old_audit_logs_records_cleanup_event(monkeypatch):
    tasks_cleanup = _import_tasks_cleanup(monkeypatch)
    monkeypatch.setattr(tasks_cleanup.settings, "AUDIT_LOG_CLEANUP_ENABLED", True)
    monkeypatch.setattr(tasks_cleanup.settings, "AUDIT_LOG_RETENTION_DAYS", 365)

    session = _FakeSession()
    monkeypatch.setitem(
        sys.modules,
        "app.core.database",
        types.SimpleNamespace(sync_session_factory=lambda: session),
    )

    result = tasks_cleanup.cleanup_old_audit_logs()

    assert result == {"enabled": True, "deleted": 7, "retention_days": 365}
    assert len(session.executed) == 1
    assert len(session.added) == 1
    assert session.added[0].action == "audit_log_cleanup"
    assert session.added[0].resource_type == "audit_log"
    assert "365 days" in session.added[0].detail
    assert session.committed is True
    assert session.closed is True


def test_cleanup_old_completed_runs_invokes_cleaners_in_order(monkeypatch):
    """A.5 后 cleanup_old_completed_runs 委托给 execute_old_runs_cleanup；
    本测试仅验证：开启时调用一次并返回 service 的结果，session.close 被触发。"""
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

    captured: dict = {}

    def fake_execute(current_session, *, days, batch_size):
        captured["session"] = current_session
        captured["days"] = days
        captured["batch_size"] = batch_size
        return {
            "plan_runs": 5,
            "suite_runs": 3,
            "test_runs": 9,
            "mobile_runs": 2,
            "deleted_objects": 5,
            "retention_days": days,
        }

    monkeypatch.setattr(tasks_cleanup, "execute_old_runs_cleanup", fake_execute)

    result = tasks_cleanup.cleanup_old_completed_runs()

    assert result == {
        "plan_runs": 5,
        "suite_runs": 3,
        "test_runs": 9,
        "mobile_runs": 2,
        "deleted_objects": 5,
        "retention_days": 7,
    }
    assert captured["session"] is session
    assert captured["days"] == 7
    assert captured["batch_size"] == 200
    assert session.closed is True


def test_cleanup_test_runs_collects_screenshots_then_deletes_rows(monkeypatch):
    """A.5 后内部 helper 已搬到 app.services.run_retention；
    保留此用例位置以便回归 service 层 execute 行为：失败时回滚 + 空结果不抛。"""
    tasks_cleanup = _import_tasks_cleanup(monkeypatch)
    monkeypatch.setattr(tasks_cleanup.settings, "RUN_CLEANUP_ENABLED", True)
    monkeypatch.setattr(tasks_cleanup.settings, "RUN_RETENTION_DAYS", 30)
    monkeypatch.setattr(tasks_cleanup.settings, "RUN_CLEANUP_BATCH_SIZE", 100)
    monkeypatch.setattr(tasks_cleanup, "load_all_models", lambda: None)

    session = _FakeSession()
    monkeypatch.setitem(
        sys.modules,
        "app.core.database",
        types.SimpleNamespace(sync_session_factory=lambda: session),
    )

    def explode(*_a, **_kw):
        raise RuntimeError("boom")

    monkeypatch.setattr(tasks_cleanup, "execute_old_runs_cleanup", explode)

    result = tasks_cleanup.cleanup_old_completed_runs()

    # 异常时返回零摘要、不抛出，session.close 被触发
    assert result == {
        "plan_runs": 0,
        "suite_runs": 0,
        "test_runs": 0,
        "mobile_runs": 0,
        "deleted_objects": 0,
    }
    assert session.closed is True
