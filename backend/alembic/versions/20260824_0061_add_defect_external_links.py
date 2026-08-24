"""Add mappings from internal defects to external issues.

Revision ID: 20260824_0061
Revises: 20260824_0060
Create Date: 2026-08-24 18:00:00
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "20260824_0061"
down_revision: Union[str, None] = "20260824_0060"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "defect_external_links",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("defect_id", sa.Integer(), nullable=False),
        sa.Column("tracker_id", sa.Integer(), nullable=False),
        sa.Column("external_key", sa.String(length=128), nullable=False),
        sa.Column("external_url", sa.String(length=1024), nullable=True),
        sa.Column("external_title", sa.String(length=512), nullable=True),
        sa.Column("external_status", sa.String(length=128), nullable=True),
        sa.Column("sync_state", sa.String(length=16), server_default="linked", nullable=False),
        sa.Column("last_synced_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_error", sa.Text(), nullable=True),
        sa.Column("created_by", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["defect_id"], ["defects.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["tracker_id"], ["bug_trackers.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["created_by"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("defect_id", "tracker_id", "external_key", name="uq_defect_external_links_key"),
    )
    op.create_index("ix_defect_external_links_defect", "defect_external_links", ["defect_id"])
    op.create_index("ix_defect_external_links_tracker", "defect_external_links", ["tracker_id"])


def downgrade() -> None:
    op.drop_index("ix_defect_external_links_tracker", table_name="defect_external_links")
    op.drop_index("ix_defect_external_links_defect", table_name="defect_external_links")
    op.drop_table("defect_external_links")
