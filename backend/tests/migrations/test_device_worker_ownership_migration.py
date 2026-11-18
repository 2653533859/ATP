"""Migration regression tests for 20261117_0092_add_device_worker_ownership."""

from __future__ import annotations

import importlib.util
from pathlib import Path
import sys

import pytest
from sqlalchemy import create_engine, inspect, text

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

MIGRATION_PATH = (
    Path(__file__).resolve().parents[2] / "alembic" / "versions" / "20261117_0092_add_device_worker_ownership.py"
)


def _load_migration():
    spec = importlib.util.spec_from_file_location("m_0092_device_worker_ownership", MIGRATION_PATH)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


def test_migration_0092_metadata_and_downgrade_guard():
    module = _load_migration()
    assert module.revision == "20261117_0092"
    assert module.down_revision == "20261113_0091"

    source = MIGRATION_PATH.read_text(encoding="utf-8")
    assert "uq_devices_worker_id_serial" in source
    assert "uq_devices_unclaimed_serial" in source
    assert "ix_devices_worker_id" in source
    assert "HAVING COUNT(*) > 1" in source


def test_local_schema_v25_upgrades_devices_preserving_rows_and_constraints():
    from app.core.local_schema import CURRENT_LOCAL_SCHEMA_VERSION, LOCAL_MIGRATIONS, ensure_local_schema

    assert CURRENT_LOCAL_SCHEMA_VERSION >= 25
    assert 25 in LOCAL_MIGRATIONS

    engine = create_engine("sqlite:///:memory:")
    with engine.begin() as conn:
        conn.exec_driver_sql(
            "CREATE TABLE devices ("
            "id INTEGER PRIMARY KEY AUTOINCREMENT, "
            "serial VARCHAR(128) NOT NULL UNIQUE, "
            "name VARCHAR(128), model VARCHAR(128), brand VARCHAR(64), "
            "os_version VARCHAR(32), sdk_version VARCHAR(16), resolution VARCHAR(32), "
            "status VARCHAR(7), ip_address VARCHAR(64), port INTEGER, description TEXT, "
            "last_seen_at DATETIME, created_at DATETIME NOT NULL, updated_at DATETIME NOT NULL"
            ")"
        )
        conn.exec_driver_sql(
            "INSERT INTO devices (serial, name, status, created_at, updated_at) "
            "VALUES ('emulator-5554', 'Legacy Phone', 'online', '2026-11-17 00:00:00', '2026-11-17 00:00:00')"
        )
        LOCAL_MIGRATIONS[25](conn)

        cols = {col["name"] for col in inspect(conn).get_columns("devices")}
        assert {"worker_id", "worker_hostname"}.issubset(cols)
        rows = conn.execute(text("SELECT id, serial, worker_id FROM devices")).fetchall()
        assert rows == [(1, "emulator-5554", None)]

        # 两个不同 worker 可共存相同 serial
        conn.exec_driver_sql(
            "INSERT INTO devices (serial, worker_id, status, created_at, updated_at) "
            "VALUES ('emulator-5554', 'win-a', 'online', '2026-11-17 00:00:00', '2026-11-17 00:00:00')"
        )
        conn.exec_driver_sql(
            "INSERT INTO devices (serial, worker_id, status, created_at, updated_at) "
            "VALUES ('emulator-5554', 'win-b', 'online', '2026-11-17 00:00:00', '2026-11-17 00:00:00')"
        )
        # 未认领设备（worker_id IS NULL）不允许重复 serial
        with pytest.raises(Exception):
            conn.exec_driver_sql(
                "INSERT INTO devices (serial, worker_id, status, created_at, updated_at) "
                "VALUES ('emulator-5554', NULL, 'online', '2026-11-17 00:00:00', '2026-11-17 00:00:00')"
            )

    fresh_engine = create_engine("sqlite:///:memory:")
    assert ensure_local_schema(fresh_engine) == CURRENT_LOCAL_SCHEMA_VERSION


def test_local_schema_v25_preserves_foreign_keys_and_child_rows_when_fk_pragma_enabled(tmp_path):
    """Ensure local SQLite v24 -> v25 upgrade with PRAGMA foreign_keys=ON does not fail or cascade-delete children."""
    from sqlalchemy import event

    from app.core.local_schema import CURRENT_LOCAL_SCHEMA_VERSION, ensure_local_schema

    db_path = tmp_path / "local_v24.sqlite3"
    engine = create_engine(f"sqlite:///{db_path}")

    @event.listens_for(engine, "connect")
    def _enable_fk(dbapi_connection, _record):
        cur = dbapi_connection.cursor()
        cur.execute("PRAGMA foreign_keys=ON")
        cur.close()

    # Bootstrap current schema first, then downgrade devices table + user_version to v24 shape with child rows.
    assert ensure_local_schema(engine) == CURRENT_LOCAL_SCHEMA_VERSION

    raw = engine.raw_connection()
    try:
        cur = raw.cursor()
        cur.execute("PRAGMA foreign_keys=OFF")
        cur.execute("DROP TABLE devices")
        cur.execute(
            "CREATE TABLE devices ("
            "id INTEGER PRIMARY KEY AUTOINCREMENT, "
            "serial VARCHAR(128) NOT NULL UNIQUE, "
            "name VARCHAR(128), model VARCHAR(128), brand VARCHAR(64), "
            "os_version VARCHAR(32), sdk_version VARCHAR(16), resolution VARCHAR(32), "
            "status VARCHAR(7), ip_address VARCHAR(64), port INTEGER, description TEXT, "
            "last_seen_at DATETIME, created_at DATETIME NOT NULL, updated_at DATETIME NOT NULL"
            ")"
        )
        cur.execute(
            "INSERT INTO devices (id, serial, name, status, created_at, updated_at) "
            "VALUES (10, 'R11-001', 'OPPO R11', 'online', '2026-11-17 00:00:00', '2026-11-17 00:00:00')"
        )
        cur.execute(
            "INSERT INTO users (id, username, email, hashed_password, role, is_active, created_at, updated_at) "
            "VALUES (1, 'admin', 'admin@example.com', 'x', 'admin', 1, '2026-11-17 00:00:00', '2026-11-17 00:00:00')"
        )
        cur.execute(
            "INSERT INTO projects (id, name, owner_id, created_at, updated_at) "
            "VALUES (1, 'P1', 1, '2026-11-17 00:00:00', '2026-11-17 00:00:00')"
        )
        # Child with ON DELETE CASCADE (device_package_snapshots)
        cur.execute(
            "INSERT INTO device_package_snapshots "
            "(id, device_id, serial, packages, source, read_at, created_at, updated_at) "
            "VALUES (1, 10, 'R11-001', '[\"com.demo\"]', 'manual', '2026-11-17 00:00:00', '2026-11-17 00:00:00', '2026-11-17 00:00:00')"
        )
        # Child with ON DELETE SET NULL (recording_records)
        cur.execute(
            "INSERT INTO recording_records "
            "(id, project_id, owner_id, kind, source, title, status, device_id, device_serial, steps, asset_ids, artifacts, summary, created_at, updated_at) "
            "VALUES (1, 1, 1, 'android', 'workbench', 'Rec', 'saved', 10, 'R11-001', '[]', '[]', '{}', '{}', '2026-11-17 00:00:00', '2026-11-17 00:00:00')"
        )
        # Child with FK to devices (mobile_special_tasks)
        cur.execute(
            "INSERT INTO mobile_special_tasks "
            "(id, project_id, name, task_type, source_type, device_scope_type, device_id, app_package, config_json, schedule_enabled, created_by, created_at, updated_at) "
            "VALUES (1, 1, 'Monkey', 'stability', 'monkey', 'single_device', 10, 'com.demo', '{}', 0, 1, '2026-11-17 00:00:00', '2026-11-17 00:00:00')"
        )
        cur.execute("PRAGMA user_version=24")
        raw.commit()
        cur.execute("PRAGMA foreign_keys=ON")
        cur.close()
    finally:
        raw.close()

    engine.dispose()
    upgraded_ver = ensure_local_schema(engine)
    assert upgraded_ver == CURRENT_LOCAL_SCHEMA_VERSION

    with engine.connect() as conn:
        # PRAGMA foreign_keys must remain ON after ensure_local_schema returns connection to pool
        assert int(conn.exec_driver_sql("PRAGMA foreign_keys").scalar_one()) == 1
        assert conn.exec_driver_sql("SELECT id, serial, worker_id FROM devices").fetchall() == [(10, "R11-001", None)]
        assert conn.exec_driver_sql("SELECT device_id FROM device_package_snapshots WHERE id=1").scalar_one() == 10
        assert conn.exec_driver_sql("SELECT device_id FROM recording_records WHERE id=1").scalar_one() == 10
        assert conn.exec_driver_sql("SELECT device_id FROM mobile_special_tasks WHERE id=1").scalar_one() == 10
    engine.dispose()


def test_migration_0092_upgrade_and_downgrade_rejects_duplicate_serials(tmp_path):
    """Execute 20261117_0092 upgrade & downgrade against real DB connection, verifying duplicate serial rejection."""
    from alembic.migration import MigrationContext
    from alembic.operations import Operations

    module = _load_migration()
    engine = create_engine(f"sqlite:///{(tmp_path / 'alembic_0092.db').as_posix()}")
    with engine.begin() as conn:
        conn.exec_driver_sql(
            "CREATE TABLE devices ("
            "id INTEGER PRIMARY KEY AUTOINCREMENT, "
            "serial VARCHAR(128) NOT NULL, "
            "name VARCHAR(128), model VARCHAR(128), brand VARCHAR(64), "
            "os_version VARCHAR(32), sdk_version VARCHAR(16), resolution VARCHAR(32), "
            "status VARCHAR(7), ip_address VARCHAR(64), port INTEGER, description TEXT, "
            "last_seen_at DATETIME, created_at DATETIME NOT NULL, updated_at DATETIME NOT NULL, "
            "CONSTRAINT uq_devices_serial UNIQUE (serial)"
            ")"
        )
        conn.exec_driver_sql(
            "INSERT INTO devices (serial, name, status, created_at, updated_at) "
            "VALUES ('emulator-5554', 'Phone A', 'online', '2026-11-17 00:00:00', '2026-11-17 00:00:00')"
        )
        with Operations.context(MigrationContext.configure(conn)):
            module.upgrade()

        # After upgrade, two workers can own the same serial
        conn.exec_driver_sql("UPDATE devices SET worker_id='win-a' WHERE id=1")
        conn.exec_driver_sql(
            "INSERT INTO devices (serial, worker_id, name, status, created_at, updated_at) "
            "VALUES ('emulator-5554', 'win-b', 'Phone B', 'online', '2026-11-17 00:00:00', '2026-11-17 00:00:00')"
        )

        # Downgrade must refuse while duplicate serials exist across workers
        with Operations.context(MigrationContext.configure(conn)):
            with pytest.raises(RuntimeError, match="无法降级 20261117_0092"):
                module.downgrade()

        # Once conflict is resolved manually, downgrade succeeds and restores unique serial
        conn.exec_driver_sql("DELETE FROM devices WHERE worker_id='win-b'")
        with Operations.context(MigrationContext.configure(conn)):
            module.downgrade()

        cols = {col["name"] for col in inspect(conn).get_columns("devices")}
        assert "worker_id" not in cols
        assert "worker_hostname" not in cols
        assert conn.execute(text("SELECT serial FROM devices")).fetchall() == [("emulator-5554",)]
    engine.dispose()
