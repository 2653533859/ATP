"""add step_results healing fields for AI case healing (P3.A)

Revision ID: 20260521_0024
Revises: 20260521_0023
Create Date: 2026-05-21 16:00:00
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = "20260521_0024"
down_revision: Union[str, None] = "20260521_0023"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "step_results",
        sa.Column("healing_suggestion", sa.Text, nullable=True),
    )
    op.add_column(
        "step_results",
        sa.Column("healing_status", sa.String(16), nullable=True),
    )
    op.add_column(
        "step_results",
        sa.Column("healing_at", sa.DateTime(timezone=True), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("step_results", "healing_at")
    op.drop_column("step_results", "healing_status")
    op.drop_column("step_results", "healing_suggestion")
