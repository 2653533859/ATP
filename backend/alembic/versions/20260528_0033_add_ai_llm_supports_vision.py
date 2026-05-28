"""Q6 P2.4: add ai llm supports_vision

Revision ID: 20260528_0033
Revises: 20260528_0032
Create Date: 2026-05-28 23:00:00
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = "20260528_0033"
down_revision: Union[str, None] = "20260528_0032"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "ai_llm_configs",
        sa.Column("supports_vision", sa.Boolean(), nullable=False, server_default=sa.false()),
    )


def downgrade() -> None:
    op.drop_column("ai_llm_configs", "supports_vision")
