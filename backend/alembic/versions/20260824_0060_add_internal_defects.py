"""Add internal project defects and execution links.

Revision ID: 20260824_0060
Revises: 20260814_0059
Create Date: 2026-08-24 16:00:00
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "20260824_0060"
down_revision: Union[str, None] = "20260814_0059"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "defects",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("project_id", sa.Integer(), nullable=False),
        sa.Column("case_id", sa.Integer(), nullable=True),
        sa.Column("title", sa.String(length=256), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("status", sa.String(length=32), server_default="open", nullable=False),
        sa.Column("priority", sa.String(length=8), server_default="P2", nullable=False),
        sa.Column("severity", sa.String(length=32), server_default="major", nullable=False),
        sa.Column("fingerprint", sa.String(length=128), nullable=True),
        sa.Column("resolution", sa.String(length=64), nullable=True),
        sa.Column("labels", sa.JSON(), server_default="[]", nullable=False),
        sa.Column("occurrence_count", sa.Integer(), server_default="1", nullable=False),
        sa.Column("last_seen_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("creator_id", sa.Integer(), nullable=True),
        sa.Column("assignee_id", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["case_id"], ["test_cases.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["creator_id"], ["users.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["assignee_id"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_defects_project_status", "defects", ["project_id", "status"])
    op.create_index("ix_defects_project_fingerprint", "defects", ["project_id", "fingerprint"])

    op.create_table(
        "defect_run_links",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("defect_id", sa.Integer(), nullable=False),
        sa.Column("run_type", sa.String(length=32), nullable=False),
        sa.Column("run_id", sa.Integer(), nullable=False),
        sa.Column("case_id", sa.Integer(), nullable=True),
        sa.Column("evidence", sa.JSON(), server_default="{}", nullable=False),
        sa.Column("linked_by", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["defect_id"], ["defects.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["case_id"], ["test_cases.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["linked_by"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("defect_id", "run_type", "run_id", name="uq_defect_run_links_defect_run"),
    )
    op.create_index("ix_defect_run_links_run", "defect_run_links", ["run_type", "run_id"])
    op.create_index("ix_defect_run_links_case", "defect_run_links", ["case_id"])


def downgrade() -> None:
    op.drop_index("ix_defect_run_links_case", table_name="defect_run_links")
    op.drop_index("ix_defect_run_links_run", table_name="defect_run_links")
    op.drop_table("defect_run_links")
    op.drop_index("ix_defects_project_fingerprint", table_name="defects")
    op.drop_index("ix_defects_project_status", table_name="defects")
    op.drop_table("defects")
