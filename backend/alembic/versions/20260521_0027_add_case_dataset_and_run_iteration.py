"""add TestCase.dataset_id + TestRun iteration fields (P3.B MVP-B)

Revision ID: 20260521_0027
Revises: 20260521_0026
Create Date: 2026-05-21 21:30:00
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = "20260521_0027"
down_revision: Union[str, None] = "20260521_0026"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "test_cases",
        sa.Column("dataset_id", sa.Integer, sa.ForeignKey("test_datasets.id"), nullable=True),
    )
    op.add_column("test_runs", sa.Column("iteration_index", sa.Integer, nullable=True))
    op.add_column("test_runs", sa.Column("iteration_data", sa.JSON, nullable=True))
    op.add_column(
        "test_runs",
        sa.Column("parent_run_id", sa.Integer, sa.ForeignKey("test_runs.id"), nullable=True),
    )
    op.create_index("ix_test_runs_parent_run_id", "test_runs", ["parent_run_id"])


def downgrade() -> None:
    op.drop_index("ix_test_runs_parent_run_id", table_name="test_runs")
    op.drop_column("test_runs", "parent_run_id")
    op.drop_column("test_runs", "iteration_data")
    op.drop_column("test_runs", "iteration_index")
    op.drop_column("test_cases", "dataset_id")
