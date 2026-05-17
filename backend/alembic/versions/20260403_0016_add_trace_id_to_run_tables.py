"""add trace id to run tables

Revision ID: 20260403_0016
Revises: 20260403_0015
Create Date: 2026-04-03 16:30:00
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "20260403_0016"
down_revision: Union[str, None] = "20260403_0015"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("test_runs", sa.Column("trace_id", sa.String(length=64), nullable=True))
    op.add_column("suite_runs", sa.Column("trace_id", sa.String(length=64), nullable=True))
    op.add_column("plan_runs", sa.Column("trace_id", sa.String(length=64), nullable=True))
    op.create_index("ix_test_runs_trace_id", "test_runs", ["trace_id"])
    op.create_index("ix_suite_runs_trace_id", "suite_runs", ["trace_id"])
    op.create_index("ix_plan_runs_trace_id", "plan_runs", ["trace_id"])


def downgrade() -> None:
    op.drop_index("ix_plan_runs_trace_id", table_name="plan_runs")
    op.drop_index("ix_suite_runs_trace_id", table_name="suite_runs")
    op.drop_index("ix_test_runs_trace_id", table_name="test_runs")
    op.drop_column("plan_runs", "trace_id")
    op.drop_column("suite_runs", "trace_id")
    op.drop_column("test_runs", "trace_id")
