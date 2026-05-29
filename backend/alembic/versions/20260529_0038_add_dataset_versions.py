"""add dataset versions

Revision ID: 20260529_0038
Revises: 20260529_0037
Create Date: 2026-05-29 18:45:00
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = "20260529_0038"
down_revision: Union[str, None] = "20260529_0037"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "test_dataset_versions",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("dataset_id", sa.Integer(), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("format", sa.String(length=16), nullable=False, server_default="json"),
        sa.Column("rows", sa.JSON(), nullable=False, server_default="[]"),
        sa.Column("schema_fields", sa.JSON(), nullable=False, server_default="[]"),
        sa.Column("validation_policy", sa.String(length=16), nullable=False, server_default="soft"),
        sa.Column("change_type", sa.String(length=32), nullable=False, server_default="manual"),
        sa.Column("created_by", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["created_by"], ["users.id"]),
        sa.ForeignKeyConstraint(["dataset_id"], ["test_datasets.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("dataset_id", "version", name="uq_test_dataset_versions_dataset_version"),
    )
    op.create_index("ix_test_dataset_versions_dataset_id", "test_dataset_versions", ["dataset_id"])


def downgrade() -> None:
    op.drop_index("ix_test_dataset_versions_dataset_id", table_name="test_dataset_versions")
    op.drop_table("test_dataset_versions")
