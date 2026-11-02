"""add remote_agents and remote_agent_devices tables for device agent tunnels

Revision ID: 20261102_0083
Revises: 20261029_0083
Create Date: 2026-11-02 10:00:00
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "20261102_0083"
down_revision: Union[str, None] = "20261029_0083"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _has_table(name: str) -> bool:
    return sa.inspect(op.get_bind()).has_table(name)


def upgrade() -> None:
    # 模型（20261012）早于本迁移合入，开启 APP_AUTO_CREATE_TABLES 的环境可能已经建出这两张表，
    # 因此按存在性守卫，保证已有库与空库都能升级到 head。
    if not _has_table("remote_agents"):
        op.create_table(
            "remote_agents",
            sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
            sa.Column("name", sa.String(length=128), nullable=False),
            sa.Column("status", sa.String(length=32), nullable=False),
            sa.Column("agent_version", sa.String(length=32), nullable=True),
            sa.Column("os_info", sa.String(length=256), nullable=True),
            sa.Column("last_seen_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
            sa.PrimaryKeyConstraint("id"),
        )
        op.create_index("ix_remote_agents_name", "remote_agents", ["name"], unique=True)

    if not _has_table("remote_agent_devices"):
        op.create_table(
            "remote_agent_devices",
            sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
            sa.Column("agent_id", sa.Integer(), nullable=False),
            sa.Column("usb_serial", sa.String(length=128), nullable=False),
            sa.Column("tunnel_port", sa.Integer(), nullable=False),
            sa.Column("model", sa.String(length=128), nullable=True),
            sa.Column("brand", sa.String(length=128), nullable=True),
            sa.Column("os_version", sa.String(length=64), nullable=True),
            sa.Column("last_seen_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
            sa.PrimaryKeyConstraint("id"),
            sa.ForeignKeyConstraint(["agent_id"], ["remote_agents.id"], ondelete="CASCADE"),
            sa.UniqueConstraint("agent_id", "usb_serial", name="uq_remote_agent_device_agent_serial"),
            sa.UniqueConstraint("tunnel_port", name="uq_remote_agent_devices_tunnel_port"),
        )
        op.create_index("ix_remote_agent_devices_agent_id", "remote_agent_devices", ["agent_id"])
        op.create_index("ix_remote_agent_devices_usb_serial", "remote_agent_devices", ["usb_serial"])


def downgrade() -> None:
    # The restored preceding revision owns these tables; keep them on downgrade.
    pass
