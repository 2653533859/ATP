"""Android Agent 草稿/回放表迁移与本地 SQLite 版本推进测试（A20/A31）。"""

import importlib.util
from pathlib import Path

from alembic.migration import MigrationContext
from alembic.operations import Operations
from sqlalchemy import create_engine, inspect, text

from app.core.local_schema import CURRENT_LOCAL_SCHEMA_VERSION, LOCAL_MIGRATIONS


def _load_migration(tmp_path):
    path = (
        Path(__file__).resolve().parents[2] / "alembic/versions/20261111_0088_add_android_agent_draft_replay_tables.py"
    )
    spec = importlib.util.spec_from_file_location("android_agent_draft_replay_migration", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _create_parent_tables(connection):
    """最小父表，供 SQLite 外键建表参考。"""
    connection.execute(text("CREATE TABLE android_agent_sessions (id INTEGER PRIMARY KEY)"))
    connection.execute(text("CREATE TABLE existing_data (id INTEGER PRIMARY KEY)"))
    connection.execute(text("INSERT INTO existing_data VALUES (1)"))


def test_android_agent_draft_replay_migration_roundtrip(tmp_path, monkeypatch):
    module = _load_migration(tmp_path)
    engine = create_engine(f"sqlite:///{(tmp_path / 'draft_replay.sqlite').as_posix()}")
    with engine.begin() as connection:
        _create_parent_tables(connection)
        monkeypatch.setattr(module, "op", Operations(MigrationContext.configure(connection)))

        module.upgrade()
        tables = set(inspect(connection).get_table_names())
        assert "android_agent_drafts" in tables
        assert "android_agent_replays" in tables

        connection.execute(
            text(
                "INSERT INTO android_agent_drafts "
                "(project_id, session_id, version, schema_version, status, content_hash, steps, assertions, "
                "variables, preconditions, blocking_issues, source_map, environment_snapshot, created_at, updated_at) "
                "VALUES (1, 1, 1, 1, 'replayable', 'hash', '[]', '[]', '[]', '[]', '[]', '{}', '{}', "
                "'2026-11-11 00:00:00', '2026-11-11 00:00:00')"
            )
        )
        connection.execute(
            text(
                "INSERT INTO android_agent_replays "
                "(project_id, session_id, draft_id, draft_version, content_hash, idempotency_key, status, "
                "initial_state_confirmed, environment_snapshot, evidence, created_at, updated_at) "
                "VALUES (1, 1, 1, 1, 'hash', 'idem-1', 'queued', 1, '{}', '{}', "
                "'2026-11-11 00:00:00', '2026-11-11 00:00:00')"
            )
        )
        # 幂等 upgrade：已存在的表不重复创建
        module.upgrade()

        module.downgrade()
        tables_after = set(inspect(connection).get_table_names())
        assert "android_agent_drafts" not in tables_after
        assert "android_agent_replays" not in tables_after
        assert connection.execute(text("SELECT count(*) FROM existing_data")).scalar_one() == 1
    engine.dispose()


def test_local_schema_version_21_creates_draft_and_replay_tables(tmp_path):
    engine = create_engine(f"sqlite:///{(tmp_path / 'local.sqlite').as_posix()}")
    with engine.begin() as connection:
        connection.execute(text("CREATE TABLE android_agent_sessions (id INTEGER PRIMARY KEY)"))
        LOCAL_MIGRATIONS[21](connection)
        LOCAL_MIGRATIONS[21](connection)  # 幂等
        inspector = inspect(connection)
        assert {"android_agent_drafts", "android_agent_replays"} <= set(inspector.get_table_names())
        draft_columns = {column["name"] for column in inspector.get_columns("android_agent_drafts")}
        assert {"content_hash", "blocking_issues", "published_case_id"} <= draft_columns
        replay_columns = {column["name"] for column in inspector.get_columns("android_agent_replays")}
        assert {"idempotency_key", "draft_version", "run_id"} <= replay_columns
    engine.dispose()
    assert CURRENT_LOCAL_SCHEMA_VERSION >= 21
