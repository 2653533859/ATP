"""Add timestamp columns required by the performance node model.

Revision ID: 20260807_0045
Revises: 20260529_0044
Create Date: 2026-08-07
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = "20260807_0045"
down_revision: Union[str, None] = "20260529_0044"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "performance_nodes",
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.add_column(
        "performance_nodes",
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )


def downgrade() -> None:
    op.drop_column("performance_nodes", "updated_at")
    op.drop_column("performance_nodes", "created_at")
