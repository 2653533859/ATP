"""Add optimistic concurrency control to Hermes session state."""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "20260914_0073"
down_revision: Union[str, None] = "20260909_0072"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "hermes_sessions",
        sa.Column("state_version", sa.Integer(), server_default="1", nullable=False),
    )


def downgrade() -> None:
    op.drop_column("hermes_sessions", "state_version")
