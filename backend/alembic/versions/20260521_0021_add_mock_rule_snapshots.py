"""add mock_rule_snapshots table for D.2 Mock version management

Revision ID: 20260521_0021
Revises: 20260520_0020
Create Date: 2026-05-21 10:00:00
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = "20260521_0021"
down_revision: Union[str, None] = "20260520_0020"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "mock_rule_snapshots",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column(
            "rule_id",
            sa.Integer,
            sa.ForeignKey("mock_rules.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        ),
        sa.Column("version", sa.Integer, nullable=False),
        sa.Column("snapshot_data", sa.JSON, nullable=False, server_default="{}"),
        sa.Column("note", sa.Text, nullable=True),
        sa.Column(
            "changed_by",
            sa.Integer,
            sa.ForeignKey("users.id"),
            nullable=False,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.UniqueConstraint(
            "rule_id", "version", name="uq_mock_rule_snapshots_rule_id_version"
        ),
    )


def downgrade() -> None:
    op.drop_table("mock_rule_snapshots")
