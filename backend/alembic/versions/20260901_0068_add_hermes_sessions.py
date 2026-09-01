"""Add project-scoped Hermes sessions and governance state."""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "20260901_0068"
down_revision: Union[str, None] = "20260901_0067"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "hermes_sessions",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("project_id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("title", sa.String(length=256), nullable=False),
        sa.Column("context_filters", sa.JSON(), nullable=False),
        sa.Column("messages", sa.JSON(), nullable=False),
        sa.Column("drafts", sa.JSON(), nullable=False),
        sa.Column("metrics", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_hermes_sessions_project_id", "hermes_sessions", ["project_id"])
    op.create_index("ix_hermes_sessions_user_id", "hermes_sessions", ["user_id"])


def downgrade() -> None:
    op.drop_index("ix_hermes_sessions_user_id", table_name="hermes_sessions")
    op.drop_index("ix_hermes_sessions_project_id", table_name="hermes_sessions")
    op.drop_table("hermes_sessions")
