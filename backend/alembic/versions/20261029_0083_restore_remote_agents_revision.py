"""Restore the remote-agent revision already applied on the Linux site.

Revision ID: 20261029_0083
Revises: 20261026_0082
"""

from alembic import op
import sqlalchemy as sa

revision = "20261029_0083"
down_revision = "20261026_0082"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Some installations created these model tables before the migration.
    inspector = sa.inspect(op.get_bind())
    if not inspector.has_table("remote_agents"):
        op.create_table(
            "remote_agents",
            sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
            sa.Column("name", sa.String(128), nullable=False),
            sa.Column("status", sa.String(32), nullable=False),
            sa.Column("agent_version", sa.String(32)),
            sa.Column("os_info", sa.String(256)),
            sa.Column("last_seen_at", sa.DateTime(timezone=True)),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        )
        op.create_index("ix_remote_agents_name", "remote_agents", ["name"], unique=True)
    if not inspector.has_table("remote_agent_devices"):
        op.create_table(
            "remote_agent_devices",
            sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
            sa.Column("agent_id", sa.Integer(), sa.ForeignKey("remote_agents.id", ondelete="CASCADE"), nullable=False),
            sa.Column("usb_serial", sa.String(128), nullable=False),
            sa.Column("tunnel_port", sa.Integer(), nullable=False, unique=True),
            sa.Column("model", sa.String(128)),
            sa.Column("brand", sa.String(128)),
            sa.Column("os_version", sa.String(64)),
            sa.Column("last_seen_at", sa.DateTime(timezone=True)),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
            sa.UniqueConstraint("agent_id", "usb_serial", name="uq_remote_agent_device_agent_serial"),
        )
        op.create_index("ix_remote_agent_devices_agent_id", "remote_agent_devices", ["agent_id"])
        op.create_index("ix_remote_agent_devices_usb_serial", "remote_agent_devices", ["usb_serial"])


def downgrade() -> None:
    op.drop_index("ix_remote_agent_devices_usb_serial", table_name="remote_agent_devices")
    op.drop_index("ix_remote_agent_devices_agent_id", table_name="remote_agent_devices")
    op.drop_table("remote_agent_devices")
    op.drop_index("ix_remote_agents_name", table_name="remote_agents")
    op.drop_table("remote_agents")
