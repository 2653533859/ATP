"""录制历史与 Web 证据记录：Alembic 迁移与 SQLite 本地库升级测试。"""

import importlib.util
from pathlib import Path

from alembic.migration import MigrationContext
from alembic.operations import Operations
from sqlalchemy import create_engine, inspect, text

from app.models import load_all_models

load_all_models()


def _load_migration():
    path = Path(__file__).resolve().parents[2] / "alembic/versions/20261113_0091_add_recording_records.py"
    spec = importlib.util.spec_from_file_location("recording_records_migration", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_recording_records_upgrade_and_downgrade(tmp_path, monkeypatch):
    module = _load_migration()
    engine = create_engine(f"sqlite:///{(tmp_path / 'migration.sqlite').as_posix()}")
    with engine.begin() as connection:
        monkeypatch.setattr(module, "op", Operations(MigrationContext.configure(connection)))

        module.upgrade()
        inspector = inspect(connection)
        assert "recording_records" in inspector.get_table_names()
        columns = {column["name"] for column in inspector.get_columns("recording_records")}
        assert {
            "id",
            "project_id",
            "owner_id",
            "kind",
            "source",
            "session_id",
            "title",
            "target_url",
            "browser",
            "device_id",
            "device_serial",
            "case_id",
            "status",
            "steps",
            "asset_ids",
            "artifacts",
            "summary",
        } <= columns

        connection.execute(
            text(
                "INSERT INTO recording_records "
                "(project_id, kind, source, session_id, title, status, steps, asset_ids, artifacts, summary) "
                "VALUES (1, 'web', 'workbench', 'sess-1', '登录录制', 'draft', '[]', '[]', '{}', '{}')"
            )
        )
        assert connection.execute(text("SELECT COUNT(*) FROM recording_records")).scalar_one() == 1

        # 重复 upgrade 幂等
        module.upgrade()

        module.downgrade()
        assert "recording_records" not in inspect(connection).get_table_names()


def test_local_sqlite_v24_migration_creates_recording_records_table(tmp_path):
    from app.core.local_schema import CURRENT_LOCAL_SCHEMA_VERSION, LOCAL_MIGRATIONS

    assert CURRENT_LOCAL_SCHEMA_VERSION >= 24
    assert 24 in LOCAL_MIGRATIONS

    engine = create_engine(f"sqlite:///{(tmp_path / 'local.sqlite').as_posix()}")
    with engine.begin() as connection:
        connection.exec_driver_sql("CREATE TABLE projects (id INTEGER PRIMARY KEY)")
        connection.exec_driver_sql("CREATE TABLE users (id INTEGER PRIMARY KEY)")
        connection.exec_driver_sql("CREATE TABLE devices (id INTEGER PRIMARY KEY)")
        connection.exec_driver_sql("CREATE TABLE test_cases (id INTEGER PRIMARY KEY)")
        LOCAL_MIGRATIONS[24](connection)
        LOCAL_MIGRATIONS[24](connection)

        inspector = inspect(connection)
        assert "recording_records" in inspector.get_table_names()
        indexes = {index["name"] for index in inspector.get_indexes("recording_records")}
        assert "ix_recording_records_project_kind_updated" in indexes
        assert "ix_recording_records_owner_updated" in indexes
        uniques = {uc["name"]: uc["column_names"] for uc in inspector.get_unique_constraints("recording_records")}
        assert uniques["uq_recording_records_project_kind_session_id"] == ["project_id", "kind", "session_id"]


def test_local_sqlite_v24_allows_same_session_across_projects_and_blocks_within_project(tmp_path):
    import pytest
    from sqlalchemy import create_engine
    from sqlalchemy.exc import IntegrityError
    from app.core.local_schema import LOCAL_MIGRATIONS

    engine = create_engine(f"sqlite:///{(tmp_path / 'local-uq.sqlite').as_posix()}")
    try:
        with engine.begin() as connection:
            connection.exec_driver_sql("CREATE TABLE projects (id INTEGER PRIMARY KEY)")
            connection.exec_driver_sql("CREATE TABLE users (id INTEGER PRIMARY KEY)")
            connection.exec_driver_sql("CREATE TABLE devices (id INTEGER PRIMARY KEY)")
            connection.exec_driver_sql("CREATE TABLE test_cases (id INTEGER PRIMARY KEY)")
            connection.exec_driver_sql("INSERT INTO projects (id) VALUES (1), (2)")
            connection.exec_driver_sql("INSERT INTO users (id) VALUES (1)")
            LOCAL_MIGRATIONS[24](connection)

            insert_sql = """
                INSERT INTO recording_records (
                    project_id, owner_id, kind, source, session_id, title, status,
                    steps, asset_ids, artifacts, summary, created_at, updated_at
                ) VALUES (?, 1, 'web', 'workbench', 'shared-sess', 'title', 'draft',
                          '[]', '[]', '{}', '{}', '2026-11-13T00:00:00Z', '2026-11-13T00:00:00Z')
            """
            connection.exec_driver_sql(insert_sql, (1,))
            connection.exec_driver_sql(insert_sql, (2,))
            with pytest.raises(IntegrityError):
                connection.exec_driver_sql(insert_sql, (1,))
    finally:
        engine.dispose()
