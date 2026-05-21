"""add project.run_retention_days_override for per-project retention (P1.4)

Revision ID: 20260521_0023
Revises: 20260521_0022
Create Date: 2026-05-21 15:00:00
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = "20260521_0023"
down_revision: Union[str, None] = "20260521_0022"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "projects",
        sa.Column("run_retention_days_override", sa.Integer, nullable=True),
    )


def downgrade() -> None:
    op.drop_column("projects", "run_retention_days_override")
