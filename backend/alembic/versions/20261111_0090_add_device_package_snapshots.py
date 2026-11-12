"""add device package snapshots

Revision ID: 20261111_0090
Revises: 20261111_0089
Create Date: 2026-11-12 18:00:00
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "20261111_0090"
down_revision: Union[str, None] = "20261111_0089"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _has_table(name: str) -> bool:
    return sa.inspect(op.get_bind()).has_table(name)


def upgrade() -> None:
    # 设备包名读取改为异步任务后，快照兼作缓存与历史记录
    if not _has_table("device_package_snapshots"):
        op.create_table(
            "device_package_snapshots",
            sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
            sa.Column("device_id", sa.Integer(), nullable=False),
            sa.Column("serial", sa.String(length=128), nullable=False),
            sa.Column("current_package", sa.String(length=128), nullable=True),
            sa.Column("current_activity", sa.String(length=256), nullable=True),
            sa.Column("packages", sa.JSON(), server_default="[]", nullable=False),
            sa.Column("source", sa.String(length=32), server_default="manual", nullable=False),
            sa.Column("triggered_by", sa.Integer(), nullable=True),
            sa.Column("read_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
            sa.ForeignKeyConstraint(["device_id"], ["devices.id"], ondelete="CASCADE"),
            sa.ForeignKeyConstraint(["triggered_by"], ["users.id"], ondelete="SET NULL"),
            sa.PrimaryKeyConstraint("id"),
        )
        op.create_index(
            "ix_device_package_snapshots_device_id",
            "device_package_snapshots",
            ["device_id"],
        )


def downgrade() -> None:
    if _has_table("device_package_snapshots"):
        op.drop_table("device_package_snapshots")
