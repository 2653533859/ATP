"""Verify Alembic migration 20261102_0083 structure and down_revision chain."""

from pathlib import Path


def test_remote_agent_tables_migration_contract() -> None:
    migration = Path(__file__).parents[2] / "alembic" / "versions" / "20261102_0083_add_remote_agent_tables.py"
    content = migration.read_text(encoding="utf-8")

    assert 'revision: str = "20261102_0083"' in content
    assert 'down_revision: Union[str, None] = "20261026_0082"' in content
    assert 'op.create_table(\n            "remote_agents"' in content
    assert 'op.create_table(\n            "remote_agent_devices"' in content
    assert 'sa.ForeignKeyConstraint(["agent_id"], ["remote_agents.id"], ondelete="CASCADE")' in content
    assert 'sa.UniqueConstraint("agent_id", "usb_serial", name="uq_remote_agent_device_agent_serial")' in content
    assert 'sa.UniqueConstraint("tunnel_port", name="uq_remote_agent_devices_tunnel_port")' in content
    assert 'op.create_index("ix_remote_agents_name", "remote_agents", ["name"], unique=True)' in content
    assert '"ix_remote_agent_devices_agent_id"' in content
    assert '"ix_remote_agent_devices_usb_serial"' in content
    assert 'op.drop_table("remote_agent_devices")' in content
    assert 'op.drop_table("remote_agents")' in content
    # 表可能已由 create_all 建出，升级必须按存在性守卫
    assert 'if not _has_table("remote_agents"):' in content
    assert 'if not _has_table("remote_agent_devices"):' in content
