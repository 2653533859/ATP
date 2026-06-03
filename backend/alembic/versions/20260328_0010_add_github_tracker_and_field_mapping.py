"""add github tracker type and field mapping

Revision ID: 20260328_0010
Revises: 20260309_0009
Create Date: 2026-03-28
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = '20260328_0010'
down_revision = '20260309_0009'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        DO $$
        BEGIN
            IF EXISTS (SELECT 1 FROM pg_type WHERE typname = 'trackertype') THEN
                ALTER TYPE trackertype ADD VALUE IF NOT EXISTS 'github';
            END IF;
        END $$;
        """
    )
    op.add_column('bug_trackers', sa.Column('field_mapping', postgresql.JSON(astext_type=sa.Text()), nullable=False, server_default=sa.text("'{}'::json")))
    op.alter_column('bug_trackers', 'field_mapping', server_default=None)


def downgrade() -> None:
    op.drop_column('bug_trackers', 'field_mapping')
