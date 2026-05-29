"""add dataset validation policy

Revision ID: 20260529_0037
Revises: 20260529_0036
Create Date: 2026-05-29 18:30:00
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = "20260529_0037"
down_revision: Union[str, None] = "20260529_0036"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "test_datasets",
        sa.Column("validation_policy", sa.String(length=16), nullable=False, server_default="soft"),
    )


def downgrade() -> None:
    op.drop_column("test_datasets", "validation_policy")
