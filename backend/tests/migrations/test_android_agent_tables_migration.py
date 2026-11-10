"""Android Agent 数据表 Alembic 迁移测试。"""

import importlib.util
from pathlib import Path

from alembic.migration import MigrationContext
from alembic.operations import Operations
from sqlalchemy import create_engine, inspect, text


def test_android_agent_tables_upgrade_and_downgrade(tmp_path, monkeypatch):
    path = Path(__file__).resolve().parents[2] / "alembic/versions/20261110_0086_add_android_agent_tables.py"
    spec = importlib.util.spec_from_file_location("android_agent_migration", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)

    engine = create_engine(f"sqlite:///{(tmp_path / 'migration.sqlite').as_posix()}")
    with engine.begin() as connection:
        connection.execute(text("CREATE TABLE existing_data (id INTEGER PRIMARY KEY)"))
        connection.execute(text("INSERT INTO existing_data VALUES (1)"))
        monkeypatch.setattr(module, "op", Operations(MigrationContext.configure(connection)))

        # 1. 执行 upgrade
        module.upgrade()
        inspector = inspect(connection)
        tables = set(inspector.get_table_names())
        assert "android_agent_sessions" in tables
        assert "android_agent_events" in tables
        assert "android_agent_commands" in tables

        # 插入测试数据验证字段映射
        connection.execute(
            text(
                "INSERT INTO android_agent_sessions "
                "(project_id, title, goal, expected_outcome, package_name) "
                "VALUES (1, 'Test', 'Goal', 'Expected', 'com.test.app')"
            )
        )
        connection.execute(
            text(
                "INSERT INTO android_agent_events "
                "(session_id, seq, event_type, payload) "
                "VALUES (1, 1, 'session_created', '{}')"
            )
        )
        connection.execute(
            text(
                "INSERT INTO android_agent_commands "
                "(session_id, seq, control_epoch, observation_id, idempotency_key, action) "
                "VALUES (1, 1, 0, 'obs-1', 'idem-1', 'tap')"
            )
        )

        # 2. 幂等 upgrade（已有表不报错）
        module.upgrade()

        # 3. 执行 downgrade
        module.downgrade()
        inspector = inspect(connection)
        tables_after = set(inspector.get_table_names())
        assert "android_agent_sessions" not in tables_after
        assert "android_agent_events" not in tables_after
        assert "android_agent_commands" not in tables_after
        assert connection.execute(text("SELECT count(*) FROM existing_data")).scalar_one() == 1

    engine.dispose()
