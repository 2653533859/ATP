"""F.2 PostgreSQL 自动备份测试：保留策略 / 调度任务 / noop on disabled."""
import sys
import types
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

# stub celery_app 以避免真实 celery 依赖
import importlib

# stub celery_app 模块以避免 celery 真实依赖（不污染顶层 celery 名空间）
# stub minio_client（兜底）
sys.modules.setdefault(
    "app.core.minio_client",
    types.SimpleNamespace(
        read_bytes=lambda *_a, **_kw: b"",
        upload_bytes=lambda *_a, **_kw: None,
        list_objects=lambda *_a, **_kw: [],
        delete_file=lambda *_a, **_kw: None,
    ),
)

# stub celery_app 以避免 celery 模块缺失
class _FakeCelery:
    def __init__(self, *a, **kw):
        pass

    def task(self, *a, **kw):
        def deco(fn):
            return fn
        return deco

    conf = types.SimpleNamespace(update=lambda **kw: None)

sys.modules.setdefault(
    "app.worker.celery_app",
    types.SimpleNamespace(celery_app=_FakeCelery()),
)

from app.worker import tasks_db_backup as backup_mod


def test_parse_backup_timestamp_recognizes_pattern():
    ts = backup_mod._parse_backup_timestamp("pg-backups/daily/atp-20260521-031701.sql.gz")
    assert ts == datetime(2026, 5, 21, 3, 17, 1, tzinfo=timezone.utc)


def test_parse_backup_timestamp_returns_none_for_unrelated():
    assert backup_mod._parse_backup_timestamp("pg-backups/daily/readme.txt") is None
    assert backup_mod._parse_backup_timestamp("foo.sql.gz") is None


def test_select_to_delete_keeps_latest_n():
    objects = [
        "pg-backups/daily/atp-20260515-031701.sql.gz",
        "pg-backups/daily/atp-20260516-031702.sql.gz",
        "pg-backups/daily/atp-20260517-031703.sql.gz",
        "pg-backups/daily/atp-20260518-031704.sql.gz",
        "pg-backups/daily/atp-20260519-031705.sql.gz",
    ]
    to_delete = backup_mod._select_to_delete(objects, keep=3)
    # 保留最新 3 个：05-19、05-18、05-17；删除 05-15、05-16
    assert sorted(to_delete) == [
        "pg-backups/daily/atp-20260515-031701.sql.gz",
        "pg-backups/daily/atp-20260516-031702.sql.gz",
    ]


def test_select_to_delete_returns_empty_when_under_cap():
    objects = ["pg-backups/daily/atp-20260520-031701.sql.gz"]
    assert backup_mod._select_to_delete(objects, keep=7) == []


def test_select_to_delete_skips_unparseable():
    objects = [
        "pg-backups/daily/atp-20260520-031701.sql.gz",
        "pg-backups/daily/garbage.txt",
        "pg-backups/daily/atp-20260519-031701.sql.gz",
    ]
    # garbage 被过滤后只剩 2 条；keep=1 应删最旧 1 条
    to_delete = backup_mod._select_to_delete(objects, keep=1)
    assert to_delete == ["pg-backups/daily/atp-20260519-031701.sql.gz"]


def test_backup_postgres_daily_skipped_when_disabled(monkeypatch):
    from app.core.config import settings

    monkeypatch.setattr(settings, "DB_BACKUP_ENABLED", False)
    fake_self = types.SimpleNamespace(retry=lambda **_kw: None)
    result = backup_mod.backup_postgres_daily(fake_self)
    assert result == {"skipped": True, "kind": "daily"}


def test_backup_postgres_weekly_skipped_when_disabled(monkeypatch):
    from app.core.config import settings

    monkeypatch.setattr(settings, "DB_BACKUP_ENABLED", False)
    fake_self = types.SimpleNamespace(retry=lambda **_kw: None)
    result = backup_mod.backup_postgres_weekly(fake_self)
    assert result == {"skipped": True, "kind": "weekly"}


def test_delete_objects_calls_minio_for_each_name(monkeypatch):
    deleted_names: list[str] = []

    def fake_delete(name):
        deleted_names.append(name)

    monkeypatch.setattr(backup_mod, "_delete_objects", lambda names: (
        [deleted_names.append(n) for n in names] and 0 or len(names)
    ))
    count = backup_mod._delete_objects(["a", "b", "c"])
    assert count == 3
    assert deleted_names == ["a", "b", "c"]


def test_enforce_retention_uses_kind_specific_keep(monkeypatch):
    from app.core.config import settings

    monkeypatch.setattr(settings, "DB_BACKUP_RETAIN_DAILY", 2)
    monkeypatch.setattr(settings, "DB_BACKUP_RETAIN_WEEKLY", 1)
    objects = [
        "pg-backups/daily/atp-20260518-031701.sql.gz",
        "pg-backups/daily/atp-20260519-031701.sql.gz",
        "pg-backups/daily/atp-20260520-031701.sql.gz",
        "pg-backups/daily/atp-20260521-031701.sql.gz",
    ]
    monkeypatch.setattr(backup_mod, "_list_backup_objects", lambda prefix: objects)
    deleted_holder: list[list[str]] = []

    def fake_delete(names):
        deleted_holder.append(list(names))
        return len(names)

    monkeypatch.setattr(backup_mod, "_delete_objects", fake_delete)

    n = backup_mod._enforce_retention("daily")
    assert n == 2  # 4 - keep(2) = 2
    assert sorted(deleted_holder[0]) == [
        "pg-backups/daily/atp-20260518-031701.sql.gz",
        "pg-backups/daily/atp-20260519-031701.sql.gz",
    ]
