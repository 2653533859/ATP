"""add stats indexes

Revision ID: 20260403_0015
Revises: 20260330_0014
Create Date: 2026-04-03 12:00:00
"""

from typing import Sequence, Union

from alembic import op


# revision identifiers, used by Alembic.
revision: str = "20260403_0015"
down_revision: Union[str, None] = "20260330_0014"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_index("ix_test_runs_status_created_at", "test_runs", ["status", "created_at"])
    op.create_index("ix_test_runs_triggered_by_created_at", "test_runs", ["triggered_by", "created_at"])
    op.create_index("ix_suite_runs_status_created_at", "suite_runs", ["status", "created_at"])
    op.create_index("ix_plan_runs_status_created_at", "plan_runs", ["status", "created_at"])


def downgrade() -> None:
    op.drop_index("ix_plan_runs_status_created_at", table_name="plan_runs")
    op.drop_index("ix_suite_runs_status_created_at", table_name="suite_runs")
    op.drop_index("ix_test_runs_triggered_by_created_at", table_name="test_runs")
    op.drop_index("ix_test_runs_status_created_at", table_name="test_runs")
