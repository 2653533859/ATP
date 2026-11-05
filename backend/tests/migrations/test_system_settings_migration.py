"""系统设置迁移可从现有库升级，也可安全降级。"""

import importlib.util
from pathlib import Path

from alembic.migration import MigrationContext
from alembic.operations import Operations
from sqlalchemy import create_engine, inspect, text


def test_system_settings_upgrade_and_downgrade(tmp_path, monkeypatch):
    path = Path(__file__).resolve().parents[2] / "alembic/versions/20261104_0085_add_system_settings.py"
    spec = importlib.util.spec_from_file_location("system_settings_migration", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    engine = create_engine(f"sqlite:///{(tmp_path / 'migration.sqlite').as_posix()}")
    with engine.begin() as connection:
        connection.execute(text("CREATE TABLE existing_data (id INTEGER PRIMARY KEY)"))
        connection.execute(text("INSERT INTO existing_data VALUES (1)"))
        monkeypatch.setattr(module, "op", Operations(MigrationContext.configure(connection)))
        module.upgrade()
        connection.execute(text("INSERT INTO system_settings (key, value_encrypted) VALUES ('test', 'ciphertext')"))
        module.upgrade()  # 本地 create_all 已建表时保留现有值
        assert connection.execute(text("SELECT value_encrypted FROM system_settings")).scalar_one() == "ciphertext"
        module.downgrade()
        assert not inspect(connection).has_table("system_settings")
        assert connection.execute(text("SELECT count(*) FROM existing_data")).scalar_one() == 1
    engine.dispose()
