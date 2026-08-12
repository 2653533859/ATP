"""add MinIO-backed dataset references

Revision ID: 20260812_0055
Revises: 20260811_0054
"""

from alembic import op
import sqlalchemy as sa


revision = "20260812_0055"
down_revision = "20260811_0054"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "test_datasets",
        sa.Column("storage_mode", sa.String(length=16), server_default="database", nullable=False),
    )
    op.add_column("test_datasets", sa.Column("object_name", sa.String(length=512), nullable=True))
    op.add_column("test_datasets", sa.Column("row_count", sa.Integer(), nullable=True))
    op.add_column(
        "test_dataset_versions",
        sa.Column("storage_mode", sa.String(length=16), server_default="database", nullable=False),
    )
    op.add_column("test_dataset_versions", sa.Column("object_name", sa.String(length=512), nullable=True))
    op.add_column("test_dataset_versions", sa.Column("row_count", sa.Integer(), nullable=True))
    op.execute("UPDATE test_datasets SET row_count = json_array_length(rows)")
    op.execute("UPDATE test_dataset_versions SET row_count = json_array_length(rows)")


def downgrade() -> None:
    op.drop_column("test_dataset_versions", "row_count")
    op.drop_column("test_dataset_versions", "object_name")
    op.drop_column("test_dataset_versions", "storage_mode")
    op.drop_column("test_datasets", "row_count")
    op.drop_column("test_datasets", "object_name")
    op.drop_column("test_datasets", "storage_mode")
