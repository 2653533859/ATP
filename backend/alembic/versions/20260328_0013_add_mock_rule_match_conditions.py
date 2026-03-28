"""add mock rule match conditions column

Revision ID: 20260328_0013
Revises: 20260328_0012
Create Date: 2026-03-28
"""
from alembic import op
import sqlalchemy as sa


revision = '20260328_0013'
down_revision = '20260328_0012'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        'mock_rules',
        sa.Column('match_conditions', sa.JSON(), nullable=False, server_default=sa.text("'{}'")),
    )
    op.alter_column('mock_rules', 'match_conditions', server_default=None)


def downgrade() -> None:
    op.drop_column('mock_rules', 'match_conditions')
