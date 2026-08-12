"""add project lifecycle status

Revision ID: 20260811_0054
Revises: 20260807_0053
"""

from alembic import op
import sqlalchemy as sa


revision = "20260811_0054"
down_revision = "20260807_0053"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "projects",
        sa.Column("status", sa.String(length=16), server_default="active", nullable=False),
    )


def downgrade() -> None:
    op.drop_column("projects", "status")
