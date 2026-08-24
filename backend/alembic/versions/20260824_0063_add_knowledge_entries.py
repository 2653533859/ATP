"""Add project-aware knowledge hub entries."""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "20260824_0063"
down_revision: Union[str, None] = "20260824_0062"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "knowledge_entries",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("project_id", sa.Integer(), nullable=True),
        sa.Column("source_type", sa.String(length=32), nullable=False, server_default="experience"),
        sa.Column("title", sa.String(length=256), nullable=False),
        sa.Column("summary", sa.Text(), nullable=True),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("source_ref", sa.String(length=512), nullable=True),
        sa.Column("tags", sa.JSON(), nullable=False, server_default="[]"),
        sa.Column("status", sa.String(length=16), nullable=False, server_default="draft"),
        sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("author_id", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["author_id"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_knowledge_entries_project_status",
        "knowledge_entries",
        ["project_id", "status"],
    )
    op.create_index(
        "ix_knowledge_entries_project_source",
        "knowledge_entries",
        ["project_id", "source_type"],
    )
    op.create_index(
        "ix_knowledge_entries_project_updated",
        "knowledge_entries",
        ["project_id", "updated_at"],
    )


def downgrade() -> None:
    op.drop_index("ix_knowledge_entries_project_updated", table_name="knowledge_entries")
    op.drop_index("ix_knowledge_entries_project_source", table_name="knowledge_entries")
    op.drop_index("ix_knowledge_entries_project_status", table_name="knowledge_entries")
    op.drop_table("knowledge_entries")
