"""add auto create bugs to test plans

Revision ID: 20260328_0011
Revises: 20260328_0010
Create Date: 2026-03-28
"""
from alembic import op
import sqlalchemy as sa


revision = '20260328_0011'
down_revision = '20260328_0010'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column('test_plans', sa.Column('auto_create_bugs', sa.Boolean(), nullable=False, server_default=sa.false()))
    op.alter_column('test_plans', 'auto_create_bugs', server_default=None)


def downgrade() -> None:
    op.drop_column('test_plans', 'auto_create_bugs')
