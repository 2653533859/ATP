"""Add replay artifacts for Android special-test incidents.

Revision ID: 20260814_0058
Revises: 20260813_0057
Create Date: 2026-08-14 12:00:00
"""

from typing import Sequence, Union

from alembic import op


revision: str = "20260814_0058"
down_revision: Union[str, None] = "20260813_0057"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # PostgreSQL enum values cannot be removed safely in a downgrade.  Keeping
    # the downgrade empty is preferable to rewriting an enum used by existing
    # mobile run artifacts.
    op.execute("ALTER TYPE artifact_type ADD VALUE IF NOT EXISTS 'replay'")


def downgrade() -> None:
    pass
