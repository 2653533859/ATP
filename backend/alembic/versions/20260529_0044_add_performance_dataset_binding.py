"""Bind performance tests and runs to immutable dataset versions.

Revision ID: 20260529_0044
Revises: 20260529_0043
Create Date: 2026-08-07 16:45:00
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = "20260529_0044"
down_revision: Union[str, None] = "20260529_0043"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("performance_tests", sa.Column("dataset_id", sa.Integer(), nullable=True))
    op.create_foreign_key(
        "fk_performance_tests_dataset_id_test_datasets",
        "performance_tests",
        "test_datasets",
        ["dataset_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.add_column("performance_runs", sa.Column("dataset_id", sa.Integer(), nullable=True))
    op.add_column("performance_runs", sa.Column("dataset_version", sa.Integer(), nullable=True))
    op.create_foreign_key(
        "fk_performance_runs_dataset_id_test_datasets",
        "performance_runs",
        "test_datasets",
        ["dataset_id"],
        ["id"],
        ondelete="SET NULL",
    )


def downgrade() -> None:
    op.drop_constraint(
        "fk_performance_runs_dataset_id_test_datasets",
        "performance_runs",
        type_="foreignkey",
    )
    op.drop_column("performance_runs", "dataset_version")
    op.drop_column("performance_runs", "dataset_id")
    op.drop_constraint(
        "fk_performance_tests_dataset_id_test_datasets",
        "performance_tests",
        type_="foreignkey",
    )
    op.drop_column("performance_tests", "dataset_id")
