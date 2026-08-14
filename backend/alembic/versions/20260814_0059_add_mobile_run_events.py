"""Add persistent execution events for Android special-test runs.

Revision ID: 20260814_0059
Revises: 20260814_0058
Create Date: 2026-08-14 14:30:00
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "20260814_0059"
down_revision: Union[str, None] = "20260814_0058"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "mobile_run_events",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("run_id", sa.Integer(), nullable=False),
        sa.Column("sequence", sa.Integer(), nullable=False),
        sa.Column("event_time", sa.DateTime(timezone=True), nullable=False),
        sa.Column("event_type", sa.String(length=64), nullable=False),
        sa.Column("phase", sa.String(length=64), nullable=True),
        sa.Column("action", sa.String(length=128), nullable=True),
        sa.Column("level", sa.String(length=16), nullable=True),
        sa.Column("message", sa.Text(), nullable=True),
        sa.Column("parameters_json", sa.JSON(), server_default="{}", nullable=False),
        sa.Column("result_json", sa.JSON(), server_default="{}", nullable=False),
        sa.Column("duration_ms", sa.Integer(), nullable=True),
        sa.ForeignKeyConstraint(["run_id"], ["mobile_special_runs.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_mobile_run_events_run_id",
        "mobile_run_events",
        ["run_id"],
    )
    op.create_index(
        "ix_mobile_run_events_run_sequence",
        "mobile_run_events",
        ["run_id", "sequence"],
    )


def downgrade() -> None:
    op.drop_index("ix_mobile_run_events_run_sequence", table_name="mobile_run_events")
    op.drop_index("ix_mobile_run_events_run_id", table_name="mobile_run_events")
    op.drop_table("mobile_run_events")
