"""add cloud_run_summaries table for desktop sync aggregation (D3)

Revision ID: 20261026_0082
Revises: 20261015_0081
Create Date: 2026-10-26 12:30:00
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "20261026_0082"
down_revision: Union[str, None] = "20261015_0081"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "cloud_run_summaries",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("client_id", sa.String(length=64), nullable=False),
        sa.Column("machine_name", sa.String(length=64), nullable=False),
        sa.Column("unique_key", sa.String(length=128), nullable=False),
        sa.Column("run_type", sa.String(length=32), nullable=False),
        sa.Column("run_id", sa.Integer(), nullable=False),
        sa.Column("project_name", sa.String(length=128), nullable=False),
        sa.Column("project_code", sa.String(length=64), nullable=False),
        sa.Column("title", sa.String(length=256), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("duration_ms", sa.Integer(), nullable=True),
        sa.Column("triggered_by", sa.String(length=64), server_default="admin", nullable=False),
        sa.Column("environment", sa.String(length=64), nullable=True),
        sa.Column("metrics", sa.JSON(), server_default="{}", nullable=False),
        sa.Column("error_summary", sa.Text(), nullable=True),
        sa.Column("steps_summary", sa.JSON(), server_default="[]", nullable=False),
        sa.Column("reported_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("unique_key", name="uq_cloud_run_summaries_unique_key"),
    )
    op.create_index("ix_cloud_run_summaries_client_id", "cloud_run_summaries", ["client_id"])
    op.create_index("ix_cloud_run_summaries_unique_key", "cloud_run_summaries", ["unique_key"])
    op.create_index("ix_cloud_run_summaries_run_type", "cloud_run_summaries", ["run_type"])
    op.create_index("ix_cloud_run_summaries_project_code", "cloud_run_summaries", ["project_code"])
    op.create_index("ix_cloud_run_summaries_status", "cloud_run_summaries", ["status"])


def downgrade() -> None:
    op.drop_index("ix_cloud_run_summaries_status", table_name="cloud_run_summaries")
    op.drop_index("ix_cloud_run_summaries_project_code", table_name="cloud_run_summaries")
    op.drop_index("ix_cloud_run_summaries_run_type", table_name="cloud_run_summaries")
    op.drop_index("ix_cloud_run_summaries_unique_key", table_name="cloud_run_summaries")
    op.drop_index("ix_cloud_run_summaries_client_id", table_name="cloud_run_summaries")
    op.drop_table("cloud_run_summaries")
