"""add runs composite indexes for keyset pagination

Revision ID: 20260520_0020
Revises: 20260518_0019
Create Date: 2026-05-20 12:00:00
"""

from typing import Sequence, Union

from alembic import op


revision: str = "20260520_0020"
down_revision: Union[str, None] = "20260518_0019"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_index(
        "ix_test_runs_case_status_created",
        "test_runs",
        ["case_id", "status", "created_at"],
    )
    op.create_index(
        "ix_test_runs_case_id_created_at",
        "test_runs",
        ["case_id", "created_at"],
    )


def downgrade() -> None:
    op.drop_index("ix_test_runs_case_id_created_at", table_name="test_runs")
    op.drop_index("ix_test_runs_case_status_created", table_name="test_runs")
