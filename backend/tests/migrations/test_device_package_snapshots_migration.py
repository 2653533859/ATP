"""设备包名快照：Alembic 迁移与 SQLite 本地库升级测试。"""

import importlib.util
from pathlib import Path

from alembic.migration import MigrationContext
from alembic.operations import Operations
from sqlalchemy import create_engine, inspect, text

from app.models import load_all_models

load_all_models()


def _load_migration():
    path = Path(__file__).resolve().parents[2] / "alembic/versions/20261111_0090_add_device_package_snapshots.py"
    spec = importlib.util.spec_from_file_location("device_package_snapshots_migration", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_device_package_snapshots_upgrade_and_downgrade(tmp_path, monkeypatch):
    module = _load_migration()
    engine = create_engine(f"sqlite:///{(tmp_path / 'migration.sqlite').as_posix()}")
    with engine.begin() as connection:
        monkeypatch.setattr(module, "op", Operations(MigrationContext.configure(connection)))

        module.upgrade()
        inspector = inspect(connection)
        assert "device_package_snapshots" in inspector.get_table_names()
        columns = {column["name"] for column in inspector.get_columns("device_package_snapshots")}
        assert {"device_id", "serial", "packages", "source", "read_at"} <= columns

        connection.execute(
            text(
                "INSERT INTO device_package_snapshots "
                "(device_id, serial, current_package, packages, source, read_at) "
                "VALUES (3, '172.16.101.11:5555', 'com.demo.app', '[]', 'refresh', '2026-11-12 10:00:00')"
            )
        )
        assert connection.execute(text("SELECT COUNT(*) FROM device_package_snapshots")).scalar_one() == 1

        # 重复 upgrade 幂等
        module.upgrade()

        module.downgrade()
        assert "device_package_snapshots" not in inspect(connection).get_table_names()


def test_local_sqlite_v23_migration_creates_snapshot_table(tmp_path):
    from app.core.local_schema import CURRENT_LOCAL_SCHEMA_VERSION, LOCAL_MIGRATIONS

    assert CURRENT_LOCAL_SCHEMA_VERSION >= 23
    assert 23 in LOCAL_MIGRATIONS

    engine = create_engine(f"sqlite:///{(tmp_path / 'local.sqlite').as_posix()}")
    with engine.begin() as connection:
        connection.exec_driver_sql("CREATE TABLE devices (id INTEGER PRIMARY KEY)")
        connection.exec_driver_sql("CREATE TABLE users (id INTEGER PRIMARY KEY)")
        LOCAL_MIGRATIONS[23](connection)
        # 幂等：重复执行不报错
        LOCAL_MIGRATIONS[23](connection)

        inspector = inspect(connection)
        assert "device_package_snapshots" in inspector.get_table_names()
        columns = {column["name"] for column in inspector.get_columns("device_package_snapshots")}
        assert {"device_id", "serial", "packages", "source", "read_at"} <= columns
        indexes = {index["name"] for index in inspector.get_indexes("device_package_snapshots")}
        assert "ix_device_package_snapshots_device_id" in indexes
