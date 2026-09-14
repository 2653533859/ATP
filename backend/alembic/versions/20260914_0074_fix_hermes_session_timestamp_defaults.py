"""Add missing timestamp defaults to Hermes sessions."""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "20260914_0074"
down_revision: Union[str, None] = "20260914_0073"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    for column_name in ("created_at", "updated_at"):
        op.alter_column(
            "hermes_sessions",
            column_name,
            existing_type=sa.DateTime(timezone=True),
            existing_nullable=False,
            server_default=sa.func.now(),
        )


def downgrade() -> None:
    for column_name in reversed(("created_at", "updated_at")):
        op.alter_column(
            "hermes_sessions",
            column_name,
            existing_type=sa.DateTime(timezone=True),
            existing_nullable=False,
            server_default=None,
        )
