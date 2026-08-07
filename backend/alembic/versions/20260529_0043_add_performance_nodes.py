"""Add performance load-injector nodes and run assignments.

Revision ID: 20260529_0043
Revises: 20260529_0042
Create Date: 2026-08-07 16:00:00
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = "20260529_0043"
down_revision: Union[str, None] = "20260529_0042"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "performance_nodes",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("node_id", sa.String(length=128), nullable=False),
        sa.Column("name", sa.String(length=128), nullable=False),
        sa.Column("queue_name", sa.String(length=128), nullable=False, server_default="performance"),
        sa.Column("status", sa.String(length=32), nullable=False, server_default="offline"),
        sa.Column("enabled", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("labels", sa.JSON(), nullable=False, server_default=sa.text("'{}'")),
        sa.Column("capabilities", sa.JSON(), nullable=False, server_default=sa.text("'{}'")),
        sa.Column("max_vus", sa.Integer(), nullable=True),
        sa.Column("max_concurrency", sa.Integer(), nullable=True),
        sa.Column("egress_allowlist", sa.JSON(), nullable=False, server_default=sa.text("'[]'")),
        sa.Column("last_heartbeat_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_error", sa.Text(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("node_id", name="uq_performance_nodes_node_id"),
    )
    op.add_column("performance_tests", sa.Column("schedule_node_id", sa.Integer(), nullable=True))
    op.create_foreign_key(
        "fk_performance_tests_schedule_node_id_performance_nodes",
        "performance_tests",
        "performance_nodes",
        ["schedule_node_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.add_column("performance_runs", sa.Column("performance_node_id", sa.Integer(), nullable=True))
    op.create_foreign_key(
        "fk_performance_runs_performance_node_id_performance_nodes",
        "performance_runs",
        "performance_nodes",
        ["performance_node_id"],
        ["id"],
        ondelete="SET NULL",
    )


def downgrade() -> None:
    op.drop_constraint(
        "fk_performance_runs_performance_node_id_performance_nodes",
        "performance_runs",
        type_="foreignkey",
    )
    op.drop_column("performance_runs", "performance_node_id")
    op.drop_constraint(
        "fk_performance_tests_schedule_node_id_performance_nodes",
        "performance_tests",
        type_="foreignkey",
    )
    op.drop_column("performance_tests", "schedule_node_id")
    op.drop_table("performance_nodes")
