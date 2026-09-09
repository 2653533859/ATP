"""Add missing timestamp defaults to Web asset tables."""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "20260909_0071"
down_revision: Union[str, None] = "20260908_0070"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


_TABLES = ("web_element_assets", "web_page_objects", "web_visual_baselines")


def upgrade() -> None:
    for table_name in _TABLES:
        op.alter_column(
            table_name,
            "created_at",
            existing_type=sa.DateTime(timezone=True),
            existing_nullable=False,
            server_default=sa.func.now(),
        )
        op.alter_column(
            table_name,
            "updated_at",
            existing_type=sa.DateTime(timezone=True),
            existing_nullable=False,
            server_default=sa.func.now(),
        )


def downgrade() -> None:
    for table_name in reversed(_TABLES):
        op.alter_column(
            table_name,
            "updated_at",
            existing_type=sa.DateTime(timezone=True),
            existing_nullable=False,
            server_default=None,
        )
        op.alter_column(
            table_name,
            "created_at",
            existing_type=sa.DateTime(timezone=True),
            existing_nullable=False,
            server_default=None,
        )
