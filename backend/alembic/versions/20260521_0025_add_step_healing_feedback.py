"""add step_results healing_feedback fields for AI healing user feedback (P3.A iter3)

Revision ID: 20260521_0025
Revises: 20260521_0024
Create Date: 2026-05-21 18:30:00
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = "20260521_0025"
down_revision: Union[str, None] = "20260521_0024"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "step_results",
        sa.Column("healing_feedback", sa.String(16), nullable=True),
    )
    op.add_column(
        "step_results",
        sa.Column("healing_feedback_at", sa.DateTime(timezone=True), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("step_results", "healing_feedback_at")
    op.drop_column("step_results", "healing_feedback")
