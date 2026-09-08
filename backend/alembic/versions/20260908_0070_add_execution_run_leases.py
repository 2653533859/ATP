"""Add durable execution worker leases."""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "20260908_0070"
down_revision: Union[str, None] = "20260908_0069"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "execution_run_leases",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("task_type", sa.String(length=32), nullable=False),
        sa.Column("run_id", sa.Integer(), nullable=False),
        sa.Column("lease_token", sa.String(length=64), nullable=False),
        sa.Column("worker_id", sa.String(length=255), nullable=False),
        sa.Column("celery_task_id", sa.String(length=255), nullable=True),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("acquired_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("heartbeat_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("released_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("failure_reason", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("task_type", "run_id", name="uq_execution_run_leases_target"),
    )
    op.create_index(
        "ix_execution_run_leases_status_expires",
        "execution_run_leases",
        ["status", "expires_at"],
    )


def downgrade() -> None:
    op.drop_index("ix_execution_run_leases_status_expires", table_name="execution_run_leases")
    op.drop_table("execution_run_leases")
