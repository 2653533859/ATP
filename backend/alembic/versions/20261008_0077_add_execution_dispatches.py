"""Durable suite publication intents.

Revision ID: 20261008_0077
Revises: 20261007_0076
"""

from alembic import op
import sqlalchemy as sa

revision: str = "20261008_0077"
down_revision: str = "20261007_0076"
branch_labels: str | None = None
depends_on: str | None = None


def upgrade() -> None:
    op.create_table(
        "execution_dispatches",
        sa.Column("id", sa.String(32), primary_key=True),
        sa.Column("project_id", sa.Integer(), sa.ForeignKey("projects.id", ondelete="CASCADE"), nullable=False),
        sa.Column("run_id", sa.Integer(), nullable=False),
        sa.Column("run_identity", sa.String(32), nullable=False),
        sa.Column("task_name", sa.String(64), nullable=False),
        sa.Column("queue", sa.String(128), nullable=False),
        sa.Column("mode", sa.String(16), nullable=False),
        sa.Column("args_ciphertext", sa.Text(), nullable=False),
        sa.Column("status", sa.String(16), nullable=False, server_default="pending"),
        sa.Column("attempt_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("claim_token", sa.String(32)),
        sa.Column("claimed_at", sa.DateTime(timezone=True)),
        sa.Column("submitted_at", sa.DateTime(timezone=True)),
        sa.Column("error_code", sa.String(64)),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("task_name", "run_identity", name="uq_execution_dispatches_task_identity"),
    )
    op.create_index(
        "ix_execution_dispatches_mode_status_created", "execution_dispatches", ["mode", "status", "created_at"]
    )


def downgrade() -> None:
    op.drop_index("ix_execution_dispatches_mode_status_created", table_name="execution_dispatches")
    op.drop_table("execution_dispatches")
