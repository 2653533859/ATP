"""add mock rule advanced fields

Revision ID: 20260328_0012
Revises: 20260328_0011
Create Date: 2026-03-28
"""
from alembic import op
import sqlalchemy as sa


revision = '20260328_0012'
down_revision = '20260328_0011'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column('mock_rules', sa.Column('render_template', sa.Boolean(), nullable=False, server_default=sa.false()))
    op.add_column('mock_rules', sa.Column('record_requests', sa.Boolean(), nullable=False, server_default=sa.false()))
    op.add_column('mock_rules', sa.Column('version', sa.Integer(), nullable=False, server_default='1'))
    op.add_column('mock_rules', sa.Column('recorded_samples', sa.JSON(), nullable=False, server_default=sa.text("'[]'")))
    op.alter_column('mock_rules', 'render_template', server_default=None)
    op.alter_column('mock_rules', 'record_requests', server_default=None)
    op.alter_column('mock_rules', 'version', server_default=None)
    op.alter_column('mock_rules', 'recorded_samples', server_default=None)


def downgrade() -> None:
    op.drop_column('mock_rules', 'recorded_samples')
    op.drop_column('mock_rules', 'version')
    op.drop_column('mock_rules', 'record_requests')
    op.drop_column('mock_rules', 'render_template')
