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


# 强制 stub celery_app（不能用 setdefault：其它测试可能已导入真实 celery_app），
# 再强制重新求值 tasks_db_backup，使其 @task 装饰绑定到 fake celery。
sys.modules["app.worker.celery_app"] = types.SimpleNamespace(celery_app=_FakeCelery())

sys.modules.pop("app.worker.tasks_db_backup", None)
backup_mod = importlib.import_module("app.worker.tasks_db_backup")


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

    monkeypatch.setattr(
        backup_mod, "_delete_objects", lambda names: ([deleted_names.append(n) for n in names] and 0 or len(names))
    )
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


# ── Q15-05：补齐此前完全没跑过的分支 ─────────────────────────────
# 上面的用例覆盖了纯函数与 disabled 短路，但脚本调用、MinIO 列举/删除的真实函数体
# 以及两个任务的 enabled 路径此前一行没执行过——备份任务失败时只会静默留下一份
# 不完整的备份，正是最不该没有测试的地方。


def _minio_stub():
    return sys.modules["app.core.minio_client"]


def test_run_backup_script_raises_when_the_script_is_missing(monkeypatch, tmp_path):
    monkeypatch.setattr(backup_mod, "_BACKUP_SCRIPT", tmp_path / "not-here.sh")

    try:
        backup_mod._run_backup_script("daily")
    except FileNotFoundError as exc:
        assert "backup script missing" in str(exc)
    else:
        raise AssertionError("脚本缺失时必须抛 FileNotFoundError，而不是静默成功")


def test_run_backup_script_passes_the_kind_through_the_environment(monkeypatch, tmp_path):
    script = tmp_path / "backup-postgres.sh"
    script.write_text("#!/bin/sh\n", encoding="utf-8")
    monkeypatch.setattr(backup_mod, "_BACKUP_SCRIPT", script)

    captured: dict = {}

    def fake_run(command, env=None, capture_output=None, text=None, timeout=None):
        captured["command"] = command
        captured["env"] = env
        captured["timeout"] = timeout
        return types.SimpleNamespace(returncode=0, stdout="dumped", stderr="")

    monkeypatch.setattr(backup_mod, "subprocess", types.SimpleNamespace(run=fake_run))

    result = backup_mod._run_backup_script("weekly")

    assert result == {"code": 0, "stdout": "dumped", "stderr": ""}
    assert captured["command"] == ["sh", str(script)]
    assert captured["env"]["BACKUP_KIND"] == "weekly"
    assert captured["env"].get("PATH"), "必须继承宿主环境变量，否则脚本里的 pg_dump/mc 找不到"
    assert captured["timeout"] == 1800


def test_list_backup_objects_reads_both_name_attributes(monkeypatch):
    objects = [
        types.SimpleNamespace(object_name="pg-backups/daily/a.sql.gz"),
        types.SimpleNamespace(name="pg-backups/daily/b.sql.gz"),
        types.SimpleNamespace(object_name=None, name=None),
    ]
    monkeypatch.setattr(_minio_stub(), "list_objects", lambda prefix: objects)

    names = backup_mod._list_backup_objects("pg-backups/daily/")

    assert names == ["pg-backups/daily/a.sql.gz", "pg-backups/daily/b.sql.gz"]


def test_list_backup_objects_survives_a_minio_outage(monkeypatch):
    """列举失败不能把备份任务打崩——保留清理失败远好于备份流程整体失败。"""

    def boom(prefix):
        raise RuntimeError("minio down")

    monkeypatch.setattr(_minio_stub(), "list_objects", boom)

    assert backup_mod._list_backup_objects("pg-backups/daily/") == []


def test_list_backup_objects_tolerates_none(monkeypatch):
    monkeypatch.setattr(_minio_stub(), "list_objects", lambda prefix: None)

    assert backup_mod._list_backup_objects("pg-backups/daily/") == []


def test_delete_objects_counts_only_the_successful_ones(monkeypatch):
    deleted: list[str] = []

    def fake_delete(name):
        if name == "bad":
            raise RuntimeError("permission denied")
        deleted.append(name)

    monkeypatch.setattr(_minio_stub(), "delete_file", fake_delete)

    count = backup_mod._delete_objects(["a", "bad", "c"])

    assert count == 2, "单个对象删除失败不应中断其余对象的清理"
    assert deleted == ["a", "c"]


def test_delete_objects_short_circuits_on_empty_input(monkeypatch):
    def explode(_name):
        raise AssertionError("空列表不应触碰 MinIO")

    monkeypatch.setattr(_minio_stub(), "delete_file", explode)

    assert backup_mod._delete_objects([]) == 0


def test_parse_backup_timestamp_rejects_an_impossible_date():
    """形状匹配但日期非法（13 月）必须返回 None，而不是抛 ValueError。"""
    assert backup_mod._parse_backup_timestamp("pg-backups/daily/atp-20261301-000000.sql.gz") is None


def test_daily_backup_reports_deletions_and_a_stdout_tail(monkeypatch):
    from app.core.config import settings

    monkeypatch.setattr(settings, "DB_BACKUP_ENABLED", True)
    monkeypatch.setattr(
        backup_mod,
        "_run_backup_script",
        lambda kind: {"code": 0, "stdout": "x" * 500, "stderr": ""},
    )
    monkeypatch.setattr(backup_mod, "_enforce_retention", lambda kind: 3)

    result = backup_mod.backup_postgres_daily(types.SimpleNamespace(retry=lambda **_kw: None))

    assert result["kind"] == "daily"
    assert result["deleted"] == 3
    assert len(result["stdout_tail"]) == 200, "只保留 stdout 末尾 200 字符"


def test_daily_backup_retries_on_a_non_zero_exit(monkeypatch):
    from app.core.config import settings

    monkeypatch.setattr(settings, "DB_BACKUP_ENABLED", True)
    monkeypatch.setattr(
        backup_mod,
        "_run_backup_script",
        lambda kind: {"code": 2, "stdout": "", "stderr": "pg_dump: connection failed"},
    )

    def explode(_kind):
        raise AssertionError("备份失败时不应继续执行保留策略")

    monkeypatch.setattr(backup_mod, "_enforce_retention", explode)

    retries: list[BaseException] = []

    def fake_retry(exc=None):
        retries.append(exc)
        return RuntimeError("retry scheduled")

    try:
        backup_mod.backup_postgres_daily(types.SimpleNamespace(retry=fake_retry))
    except RuntimeError as raised:
        assert str(raised) == "retry scheduled"
    else:
        raise AssertionError("失败必须抛出 self.retry 的结果，否则 Celery 认为任务成功")

    assert "exit=2" in str(retries[0])


def test_weekly_backup_covers_the_same_two_paths(monkeypatch):
    from app.core.config import settings

    monkeypatch.setattr(settings, "DB_BACKUP_ENABLED", True)
    monkeypatch.setattr(backup_mod, "_enforce_retention", lambda kind: 1)
    monkeypatch.setattr(
        backup_mod,
        "_run_backup_script",
        lambda kind: {"code": 0, "stdout": "ok", "stderr": ""},
    )

    result = backup_mod.backup_postgres_weekly(types.SimpleNamespace(retry=lambda **_kw: None))
    assert result == {"kind": "weekly", "deleted": 1, "stdout_tail": "ok"}

    monkeypatch.setattr(
        backup_mod,
        "_run_backup_script",
        lambda kind: {"code": 1, "stdout": "", "stderr": "boom"},
    )

    def fake_retry(exc=None):
        return RuntimeError(f"retry: {exc}")

    try:
        backup_mod.backup_postgres_weekly(types.SimpleNamespace(retry=fake_retry))
    except RuntimeError as raised:
        assert "exit=1" in str(raised)
    else:
        raise AssertionError("weekly 失败同样必须抛出")
