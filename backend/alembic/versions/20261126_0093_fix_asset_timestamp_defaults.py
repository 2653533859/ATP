"""fix missing timestamp server_default on api_schema_assets and api_contract_assets

Revision ID: 20261126_0093
Revises: 20261117_0092
Create Date: 2026-11-26 15:32:00
"""

from __future__ import annotations

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "20261126_0093"
down_revision: Union[str, None] = "20261117_0092"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_TARGET_TABLES = ("api_schema_assets", "api_contract_assets")


def upgrade() -> None:
    for table_name in _TARGET_TABLES:
        with op.batch_alter_table(table_name) as batch_op:
            batch_op.alter_column(
                "created_at",
                existing_type=sa.DateTime(timezone=True),
                existing_nullable=False,
                server_default=sa.func.now(),
            )
            batch_op.alter_column(
                "updated_at",
                existing_type=sa.DateTime(timezone=True),
                existing_nullable=False,
                server_default=sa.func.now(),
            )


def downgrade() -> None:
    for table_name in _TARGET_TABLES:
        with op.batch_alter_table(table_name) as batch_op:
            batch_op.alter_column(
                "updated_at",
                existing_type=sa.DateTime(timezone=True),
                existing_nullable=False,
                server_default=None,
            )
            batch_op.alter_column(
                "created_at",
                existing_type=sa.DateTime(timezone=True),
                existing_nullable=False,
                server_default=None,
            )
