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
