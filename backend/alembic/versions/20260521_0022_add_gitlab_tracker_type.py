"""add gitlab to trackertype enum (E.2)

Revision ID: 20260521_0022
Revises: 20260521_0021
Create Date: 2026-05-21 11:00:00
"""

from typing import Sequence, Union

from alembic import op


revision: str = "20260521_0022"
down_revision: Union[str, None] = "20260521_0021"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Some fresh installs still use varchar for bug_trackers.tracker_type; only
    # extend the native enum on databases that already have it.
    op.execute(
        """
        DO $$
        BEGIN
            IF EXISTS (SELECT 1 FROM pg_type WHERE typname = 'trackertype') THEN
                ALTER TYPE trackertype ADD VALUE IF NOT EXISTS 'gitlab';
            END IF;
        END $$;
        """
    )


def downgrade() -> None:
    # PostgreSQL 不支持删除 enum 值；如需回滚需重建类型
    pass
