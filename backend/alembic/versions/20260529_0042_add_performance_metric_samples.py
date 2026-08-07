"""Add resource metric samples for performance runs.

Revision ID: 20260529_0042
Revises: 20260529_0041
Create Date: 2026-08-07 14:00:00
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = "20260529_0042"
down_revision: Union[str, None] = "20260529_0041"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "performance_metric_samples",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("run_id", sa.Integer(), nullable=False),
        sa.Column("captured_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("node_id", sa.String(length=128), nullable=False),
        sa.Column("source", sa.String(length=64), nullable=False),
        sa.Column("metrics", sa.JSON(), nullable=False, server_default=sa.text("'{}'")),
        sa.Column("errors", sa.JSON(), nullable=False, server_default=sa.text("'[]'")),
        sa.ForeignKeyConstraint(
            ["run_id"],
            ["performance_runs.id"],
            name="fk_performance_metric_samples_run_id_performance_runs",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_performance_metric_samples_run_captured",
        "performance_metric_samples",
        ["run_id", "captured_at"],
    )


def downgrade() -> None:
    op.drop_index("ix_performance_metric_samples_run_captured", table_name="performance_metric_samples")
    op.drop_table("performance_metric_samples")
