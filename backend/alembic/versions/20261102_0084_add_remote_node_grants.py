"""add remote_node_grants table for D5 multi-user/project node authorization

Revision ID: 20261102_0084
Revises: 20261102_0083
Create Date: 2026-11-02 12:00:00
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "20261102_0084"
down_revision: Union[str, None] = "20261102_0083"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _has_table(name: str) -> bool:
    return sa.inspect(op.get_bind()).has_table(name)


def upgrade() -> None:
    if _has_table("remote_node_grants"):
        return
    op.create_table(
        "remote_node_grants",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("node_client_id", sa.String(length=64), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=True),
        sa.Column("project_id", sa.Integer(), nullable=True),
        sa.Column("access_level", sa.String(length=16), nullable=False),
        sa.Column("created_by_id", sa.Integer(), nullable=True),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("revoked_by_id", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint("(user_id IS NULL) <> (project_id IS NULL)", name="ck_remote_node_grants_subject_exclusive"),
        sa.ForeignKeyConstraint(["created_by_id"], ["users.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["revoked_by_id"], ["users.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_remote_node_grants_node_client_id", "remote_node_grants", ["node_client_id"], unique=False)
    op.create_index(
        "uq_remote_node_grants_active_user",
        "remote_node_grants",
        ["node_client_id", "user_id"],
        unique=True,
        postgresql_where=sa.text("revoked_at IS NULL"),
        sqlite_where=sa.text("revoked_at IS NULL"),
    )
    op.create_index(
        "uq_remote_node_grants_active_project",
        "remote_node_grants",
        ["node_client_id", "project_id"],
        unique=True,
        postgresql_where=sa.text("revoked_at IS NULL"),
        sqlite_where=sa.text("revoked_at IS NULL"),
    )


def downgrade() -> None:
    op.drop_index("uq_remote_node_grants_active_project", table_name="remote_node_grants")
    op.drop_index("uq_remote_node_grants_active_user", table_name="remote_node_grants")
    op.drop_index("ix_remote_node_grants_node_client_id", table_name="remote_node_grants")
    op.drop_table("remote_node_grants")
