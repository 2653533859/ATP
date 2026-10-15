"""add feishu to notifychannel enum (P4.1)

Revision ID: 20261015_0080
Revises: 20261008_0079
Create Date: 2026-10-15 15:00:00
"""

from typing import Sequence, Union

from alembic import op


revision: str = "20261015_0080"
down_revision: Union[str, None] = "20261008_0079"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(
        """
        DO $$
        BEGIN
            IF EXISTS (SELECT 1 FROM pg_type WHERE typname = 'notifychannel') THEN
                ALTER TYPE notifychannel ADD VALUE IF NOT EXISTS 'feishu';
            END IF;
        END $$;
        """
    )


def downgrade() -> None:
    # PostgreSQL does not support removing values from an enum type
    pass
