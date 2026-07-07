"""add config column to test_suites

Revision ID: 20260529_0039
Revises: 20260529_0038
Create Date: 2026-05-29 19:05:00
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = "20260529_0039"
down_revision: Union[str, None] = "20260529_0038"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "test_suites",
        sa.Column(
            "config",
            sa.JSON(),
            nullable=False,
            server_default=sa.text("'{}'"),
        ),
    )


def downgrade() -> None:
    op.drop_column("test_suites", "config")
