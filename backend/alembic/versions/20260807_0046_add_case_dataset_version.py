"""Add immutable dataset version binding to test cases.

Revision ID: 20260807_0046
Revises: 20260807_0045
Create Date: 2026-08-07
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = "20260807_0046"
down_revision: Union[str, None] = "20260807_0045"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("test_cases", sa.Column("dataset_version", sa.Integer(), nullable=True))


def downgrade() -> None:
    op.drop_column("test_cases", "dataset_version")
