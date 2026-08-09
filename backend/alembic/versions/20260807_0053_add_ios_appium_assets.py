"""add iOS/Appium device leases and IPA assets

Revision ID: 20260807_0053
Revises: 20260807_0052
"""

from alembic import op
import sqlalchemy as sa


revision = "20260807_0053"
down_revision = "20260807_0052"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "ios_devices",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("udid", sa.String(length=256), nullable=False),
        sa.Column("name", sa.String(length=128), nullable=True),
        sa.Column("model", sa.String(length=128), nullable=True),
        sa.Column("platform_version", sa.String(length=32), nullable=True),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("appium_server_url", sa.String(length=512), nullable=False),
        sa.Column("wda_local_port", sa.Integer(), nullable=True),
        sa.Column("ip_address", sa.String(length=64), nullable=True),
        sa.Column("port", sa.Integer(), nullable=True),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("last_seen_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("udid"),
    )
    op.create_table(
        "ios_device_leases",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("device_id", sa.Integer(), nullable=False),
        sa.Column("lease_token", sa.String(length=96), nullable=False),
        sa.Column("owner_id", sa.Integer(), nullable=True),
        sa.Column("owner_label", sa.String(length=128), nullable=False),
        sa.Column("acquired_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("heartbeat_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["device_id"], ["ios_devices.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["owner_id"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("device_id"),
        sa.UniqueConstraint("lease_token"),
    )
    op.create_index("ix_ios_device_leases_lease_token", "ios_device_leases", ["lease_token"], unique=False)
    op.create_table(
        "ios_apps",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("project_id", sa.Integer(), nullable=False),
        sa.Column("filename", sa.String(length=256), nullable=False),
        sa.Column("bundle_id", sa.String(length=256), nullable=True),
        sa.Column("version_name", sa.String(length=64), nullable=True),
        sa.Column("file_size", sa.BigInteger(), nullable=False),
        sa.Column("object_name", sa.String(length=512), nullable=False),
        sa.Column("signing_identity", sa.String(length=256), nullable=True),
        sa.Column("provisioning_profile", sa.String(length=256), nullable=True),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("uploaded_by", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["uploaded_by"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_ios_apps_project_id", "ios_apps", ["project_id"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_ios_apps_project_id", table_name="ios_apps")
    op.drop_table("ios_apps")
    op.drop_index("ix_ios_device_leases_lease_token", table_name="ios_device_leases")
    op.drop_table("ios_device_leases")
    op.drop_table("ios_devices")
