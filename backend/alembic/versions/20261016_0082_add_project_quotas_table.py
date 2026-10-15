"""add project_quotas table for multi-tenant concurrency and execution quota governance (Q4.1)

Revision ID: 20261016_0082
Revises: 20261015_0081
Create Date: 2026-10-16 02:00:00
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "20261016_0082"
down_revision: Union[str, None] = "20261015_0081"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "project_quotas",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("project_id", sa.Integer(), nullable=False),
        sa.Column("max_concurrent_runs", sa.Integer(), server_default="5", nullable=False),
        sa.Column("daily_duration_limit_seconds", sa.Integer(), server_default="28800", nullable=False),
        sa.Column("max_single_run_timeout_seconds", sa.Integer(), server_default="3600", nullable=False),
        sa.Column("over_quota_policy", sa.String(length=16), server_default="reject", nullable=False),
        sa.Column("is_enabled", sa.Boolean(), server_default="true", nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("project_id", name="uq_project_quotas_project_id"),
    )
    op.create_index("ix_project_quotas_project", "project_quotas", ["project_id"])


def downgrade() -> None:
    op.drop_index("ix_project_quotas_project", table_name="project_quotas")
    op.drop_table("project_quotas")
