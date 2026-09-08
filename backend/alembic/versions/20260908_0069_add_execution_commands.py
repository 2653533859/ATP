"""Add the unified execution command idempotency ledger."""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "20260908_0069"
down_revision: Union[str, None] = "20260901_0068"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "execution_commands",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("command_id", sa.String(length=128), nullable=False),
        sa.Column("action", sa.String(length=16), nullable=False),
        sa.Column("task_type", sa.String(length=32), nullable=False),
        sa.Column("run_id", sa.Integer(), nullable=False),
        sa.Column("project_id", sa.Integer(), nullable=True),
        sa.Column("source_status", sa.String(length=32), nullable=False),
        sa.Column("result_status", sa.String(length=32), nullable=True),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("response_json", sa.JSON(), nullable=False),
        sa.Column("error_status_code", sa.Integer(), nullable=True),
        sa.Column("error_detail", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("user_id", "command_id", name="uq_execution_commands_user_command"),
    )
    op.create_index("ix_execution_commands_project_id", "execution_commands", ["project_id"])
    op.create_index(
        "uq_execution_commands_target_action",
        "execution_commands",
        ["action", "task_type", "run_id"],
        unique=True,
        postgresql_where=sa.text("status IN ('processing', 'succeeded', 'indeterminate')"),
    )


def downgrade() -> None:
    op.drop_index("uq_execution_commands_target_action", table_name="execution_commands")
    op.drop_index("ix_execution_commands_project_id", table_name="execution_commands")
    op.drop_table("execution_commands")
