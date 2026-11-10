"""add workbench todo snoozes and archived tasks tables

Revision ID: 20261110_0087
Revises: 20261110_0086
Create Date: 2026-11-10 11:00:00
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "20261110_0087"
down_revision: Union[str, None] = "20261110_0086"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _has_table(name: str) -> bool:
    return sa.inspect(op.get_bind()).has_table(name)


def upgrade() -> None:
    if not _has_table("workbench_todo_snoozes"):
        op.create_table(
            "workbench_todo_snoozes",
            sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
            sa.Column("todo_id", sa.String(length=128), nullable=False),
            sa.Column("user_id", sa.Integer(), nullable=False),
            sa.Column("project_id", sa.Integer(), nullable=True),
            sa.Column("reason", sa.Text(), nullable=True),
            sa.Column("snoozed_until", sa.DateTime(timezone=True), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
            sa.ForeignKeyConstraint(["project_id"], ["projects.id"], ondelete="CASCADE"),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint("user_id", "todo_id", name="uq_workbench_todo_snoozes_user_todo"),
        )
        op.create_index("ix_workbench_todo_snoozes_todo_id", "workbench_todo_snoozes", ["todo_id"])
        op.create_index("ix_workbench_todo_snoozes_user_id", "workbench_todo_snoozes", ["user_id"])
        op.create_index("ix_workbench_todo_snoozes_project_id", "workbench_todo_snoozes", ["project_id"])
        op.create_index("ix_workbench_todo_snoozes_snoozed_until", "workbench_todo_snoozes", ["snoozed_until"])

    if not _has_table("workbench_archived_tasks"):
        op.create_table(
            "workbench_archived_tasks",
            sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
            sa.Column("task_type", sa.String(length=32), nullable=False),
            sa.Column("run_id", sa.Integer(), nullable=False),
            sa.Column("project_id", sa.Integer(), nullable=True),
            sa.Column("archived_by", sa.Integer(), nullable=False),
            sa.Column("archived_at", sa.DateTime(timezone=True), nullable=False),
            sa.ForeignKeyConstraint(["archived_by"], ["users.id"], ondelete="CASCADE"),
            sa.ForeignKeyConstraint(["project_id"], ["projects.id"], ondelete="CASCADE"),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint("task_type", "run_id", name="uq_workbench_archived_tasks_type_run"),
        )
        op.create_index("ix_workbench_archived_tasks_project_id", "workbench_archived_tasks", ["project_id"])


def downgrade() -> None:
    if _has_table("workbench_archived_tasks"):
        op.drop_index("ix_workbench_archived_tasks_project_id", table_name="workbench_archived_tasks")
        op.drop_table("workbench_archived_tasks")
    if _has_table("workbench_todo_snoozes"):
        op.drop_index("ix_workbench_todo_snoozes_snoozed_until", table_name="workbench_todo_snoozes")
        op.drop_index("ix_workbench_todo_snoozes_project_id", table_name="workbench_todo_snoozes")
        op.drop_index("ix_workbench_todo_snoozes_user_id", table_name="workbench_todo_snoozes")
        op.drop_index("ix_workbench_todo_snoozes_todo_id", table_name="workbench_todo_snoozes")
        op.drop_table("workbench_todo_snoozes")
