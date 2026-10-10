"""Persistent Hermes suite creation receipts.

Revision ID: 20261003_0075
Revises: 20260914_0074
"""
from alembic import op
import sqlalchemy as sa

revision = "20261003_0075"
down_revision = "20260914_0074"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "hermes_actions",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("project_id", sa.Integer(), sa.ForeignKey("projects.id", ondelete="CASCADE"), nullable=False),
        sa.Column("command_id", sa.String(64), nullable=False),
        sa.Column("action", sa.String(32), nullable=False),
        sa.Column("request_hash", sa.String(64), nullable=False),
        sa.Column("resource_id", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("user_id", "command_id", name="uq_hermes_action_command"),
    )


def downgrade():
    op.drop_table("hermes_actions")
