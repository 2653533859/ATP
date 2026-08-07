"""Add performance baselines and per-test schedules.

Revision ID: 20260529_0041
Revises: 20260529_0040
Create Date: 2026-08-07 12:00:00
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = "20260529_0041"
down_revision: Union[str, None] = "20260529_0040"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "performance_tests",
        sa.Column("baseline_run_id", sa.Integer(), nullable=True),
    )
    op.create_foreign_key(
        "fk_performance_tests_baseline_run_id_performance_runs",
        "performance_tests",
        "performance_runs",
        ["baseline_run_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.add_column(
        "performance_tests",
        sa.Column("schedule_enabled", sa.Boolean(), nullable=False, server_default=sa.false()),
    )
    op.add_column("performance_tests", sa.Column("cron_expression", sa.String(length=128), nullable=True))
    op.add_column(
        "performance_tests",
        sa.Column("schedule_timezone", sa.String(length=64), nullable=False, server_default="Asia/Shanghai"),
    )
    op.add_column("performance_tests", sa.Column("schedule_environment_id", sa.Integer(), nullable=True))
    op.create_foreign_key(
        "fk_performance_tests_schedule_environment_id_environments",
        "performance_tests",
        "environments",
        ["schedule_environment_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.add_column(
        "performance_tests",
        sa.Column("schedule_options", sa.JSON(), nullable=False, server_default=sa.text("'{}'")),
    )
    op.add_column(
        "performance_tests",
        sa.Column("last_scheduled_run_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column("performance_tests", sa.Column("next_run_at", sa.DateTime(timezone=True), nullable=True))


def downgrade() -> None:
    op.drop_column("performance_tests", "next_run_at")
    op.drop_column("performance_tests", "last_scheduled_run_at")
    op.drop_column("performance_tests", "schedule_options")
    op.drop_constraint(
        "fk_performance_tests_schedule_environment_id_environments",
        "performance_tests",
        type_="foreignkey",
    )
    op.drop_column("performance_tests", "schedule_environment_id")
    op.drop_column("performance_tests", "schedule_timezone")
    op.drop_column("performance_tests", "cron_expression")
    op.drop_column("performance_tests", "schedule_enabled")
    op.drop_constraint(
        "fk_performance_tests_baseline_run_id_performance_runs",
        "performance_tests",
        type_="foreignkey",
    )
    op.drop_column("performance_tests", "baseline_run_id")
