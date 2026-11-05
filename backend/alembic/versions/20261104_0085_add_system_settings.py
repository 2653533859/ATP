"""add encrypted system settings

Revision ID: 20261104_0085
Revises: 20261102_0084
"""

from alembic import op
import sqlalchemy as sa

revision = "20261104_0085"
down_revision = "20261102_0084"
branch_labels = None
depends_on = None


def upgrade() -> None:
    if sa.inspect(op.get_bind()).has_table("system_settings"):
        return
    op.create_table(
        "system_settings",
        sa.Column("key", sa.String(length=128), primary_key=True),
        sa.Column("value_encrypted", sa.Text(), nullable=False),
    )


def downgrade() -> None:
    op.drop_table("system_settings")
