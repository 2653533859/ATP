"""add recording records table for recoverable drafts, steps, and web evidence

Revision ID: 20261113_0091
Revises: 20261111_0090
Create Date: 2026-11-13 15:30:00
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "20261113_0091"
down_revision: Union[str, None] = "20261111_0090"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _has_table(name: str) -> bool:
    return sa.inspect(op.get_bind()).has_table(name)


def upgrade() -> None:
    if not _has_table("recording_records"):
        op.create_table(
            "recording_records",
            sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
            sa.Column("project_id", sa.Integer(), nullable=False),
            sa.Column("owner_id", sa.Integer(), nullable=True),
            sa.Column("kind", sa.String(length=16), nullable=False),
            sa.Column("source", sa.String(length=32), server_default="workbench", nullable=False),
            sa.Column("session_id", sa.String(length=64), nullable=True),
            sa.Column("title", sa.String(length=255), nullable=False),
            sa.Column("target_url", sa.String(length=1024), nullable=True),
            sa.Column("browser", sa.String(length=32), nullable=True),
            sa.Column("device_id", sa.Integer(), nullable=True),
            sa.Column("device_serial", sa.String(length=128), nullable=True),
            sa.Column("case_id", sa.Integer(), nullable=True),
            sa.Column("status", sa.String(length=24), server_default="draft", nullable=False),
            sa.Column("steps", sa.JSON(), server_default="[]", nullable=False),
            sa.Column("asset_ids", sa.JSON(), server_default="[]", nullable=False),
            sa.Column("artifacts", sa.JSON(), server_default="{}", nullable=False),
            sa.Column("summary", sa.JSON(), server_default="{}", nullable=False),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
            sa.ForeignKeyConstraint(["case_id"], ["test_cases.id"], ondelete="SET NULL"),
            sa.ForeignKeyConstraint(["device_id"], ["devices.id"], ondelete="SET NULL"),
            sa.ForeignKeyConstraint(["owner_id"], ["users.id"], ondelete="SET NULL"),
            sa.ForeignKeyConstraint(["project_id"], ["projects.id"], ondelete="CASCADE"),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint("project_id", "kind", "session_id", name="uq_recording_records_project_kind_session_id"),
        )
        op.create_index(
            "ix_recording_records_project_kind_updated",
            "recording_records",
            ["project_id", "kind", "updated_at"],
        )
        op.create_index(
            "ix_recording_records_owner_updated",
            "recording_records",
            ["owner_id", "updated_at"],
        )


def downgrade() -> None:
    if _has_table("recording_records"):
        op.drop_index("ix_recording_records_owner_updated", table_name="recording_records")
        op.drop_index("ix_recording_records_project_kind_updated", table_name="recording_records")
        op.drop_table("recording_records")
