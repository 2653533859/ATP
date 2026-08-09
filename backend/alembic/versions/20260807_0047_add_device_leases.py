"""Add device leases for mobile execution isolation.

Revision ID: 20260807_0047
Revises: 20260807_0046
Create Date: 2026-08-07
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = "20260807_0047"
down_revision: Union[str, None] = "20260807_0046"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "device_leases",
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
        sa.ForeignKeyConstraint(["device_id"], ["devices.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["owner_id"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("device_id"),
        sa.UniqueConstraint("lease_token"),
    )
    op.create_index("ix_device_leases_lease_token", "device_leases", ["lease_token"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_device_leases_lease_token", table_name="device_leases")
    op.drop_table("device_leases")
