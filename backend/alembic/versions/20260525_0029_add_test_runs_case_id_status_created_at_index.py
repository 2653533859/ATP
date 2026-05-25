"""Q5 long-tail #2: add (case_id, status, created_at) composite index on test_runs

Revision ID: 20260525_0029
Revises: 20260522_0028
Create Date: 2026-05-25 10:00:00
"""

from typing import Sequence, Union

from alembic import op


revision: str = "20260525_0029"
down_revision: Union[str, None] = "20260522_0028"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_index(
        "ix_test_runs_case_id_status_created_at",
        "test_runs",
        ["case_id", "status", "created_at"],
    )


def downgrade() -> None:
    op.drop_index("ix_test_runs_case_id_status_created_at", table_name="test_runs")
