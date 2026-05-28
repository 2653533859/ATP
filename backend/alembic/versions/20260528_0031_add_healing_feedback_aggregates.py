"""Q6 P2.1: add healing feedback aggregates

Revision ID: 20260528_0031
Revises: 20260527_0030
Create Date: 2026-05-28 21:00:00
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = "20260528_0031"
down_revision: Union[str, None] = "20260527_0030"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "healing_feedback_aggregates",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("error_fingerprint", sa.String(length=64), nullable=False),
        sa.Column("case_type", sa.String(length=32), nullable=False),
        sa.Column("total_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("adopted_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("rejected_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("adopted_rate", sa.Float(), nullable=False, server_default="0"),
        sa.Column("last_aggregated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "error_fingerprint",
            "case_type",
            name="uq_healing_feedback_aggregate_fingerprint_case_type",
        ),
    )
    op.create_index(
        "ix_healing_feedback_aggregates_case_rate",
        "healing_feedback_aggregates",
        ["case_type", "adopted_rate"],
    )


def downgrade() -> None:
    op.drop_index("ix_healing_feedback_aggregates_case_rate", table_name="healing_feedback_aggregates")
    op.drop_table("healing_feedback_aggregates")
