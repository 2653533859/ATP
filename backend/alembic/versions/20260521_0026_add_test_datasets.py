"""add test_datasets table (P3.B MVP-A)

Revision ID: 20260521_0026
Revises: 20260521_0025
Create Date: 2026-05-21 20:00:00
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = "20260521_0026"
down_revision: Union[str, None] = "20260521_0025"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "test_datasets",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("name", sa.String(128), nullable=False),
        sa.Column("description", sa.Text, nullable=True),
        sa.Column("project_id", sa.Integer, sa.ForeignKey("projects.id", ondelete="CASCADE"), nullable=False),
        sa.Column("format", sa.String(16), nullable=False, server_default="json"),
        sa.Column("rows", sa.JSON, nullable=False, server_default="[]"),
        sa.Column("creator_id", sa.Integer, sa.ForeignKey("users.id"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("project_id", "name", name="uq_test_datasets_project_name"),
    )


def downgrade() -> None:
    op.drop_table("test_datasets")
