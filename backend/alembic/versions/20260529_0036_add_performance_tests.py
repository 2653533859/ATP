"""Q8 P1: add performance testing thin slice tables

Revision ID: 20260529_0036
Revises: 20260528_0035
Create Date: 2026-05-29 00:30:00
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = "20260529_0036"
down_revision: Union[str, None] = "20260528_0035"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "performance_tests",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("project_id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(length=128), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("executor", sa.String(length=32), nullable=False),
        sa.Column("script_object_name", sa.String(length=512), nullable=False),
        sa.Column("default_options", sa.JSON(), nullable=False, server_default="{}"),
        sa.Column("creator_id", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["creator_id"], ["users.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("project_id", "name", name="uq_performance_tests_project_name"),
    )
    op.create_table(
        "performance_runs",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("performance_test_id", sa.Integer(), nullable=False),
        sa.Column("project_id", sa.Integer(), nullable=False),
        sa.Column("environment_id", sa.Integer(), nullable=True),
        sa.Column("status", sa.String(length=32), nullable=False, server_default="pending"),
        sa.Column("triggered_by", sa.Integer(), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("duration_ms", sa.Integer(), nullable=True),
        sa.Column("options_snapshot", sa.JSON(), nullable=False, server_default="{}"),
        sa.Column("summary", sa.JSON(), nullable=False, server_default="{}"),
        sa.Column("raw_result_object_name", sa.String(length=512), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["environment_id"], ["environments.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["performance_test_id"], ["performance_tests.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["triggered_by"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_performance_runs_project_created", "performance_runs", ["project_id", "created_at"])
    op.create_index("ix_performance_runs_test_created", "performance_runs", ["performance_test_id", "created_at"])


def downgrade() -> None:
    op.drop_index("ix_performance_runs_test_created", table_name="performance_runs")
    op.drop_index("ix_performance_runs_project_created", table_name="performance_runs")
    op.drop_table("performance_runs")
    op.drop_table("performance_tests")
