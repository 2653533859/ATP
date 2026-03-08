"""add case_snapshots table

Revision ID: 20260308_0005
Revises: 20260308_0004
Create Date: 2026-03-08 12:00:00
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "20260308_0005"
down_revision: Union[str, None] = "20260308_0004"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "case_snapshots",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("case_id", sa.Integer(), sa.ForeignKey("test_cases.id", ondelete="CASCADE"), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(length=256), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("tags", sa.JSON(), nullable=False, server_default=sa.text("'[]'")),
        sa.Column("config", sa.JSON(), nullable=False, server_default=sa.text("'{}'")),
        sa.Column("updated_by", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_unique_constraint(
        "uq_case_snapshots_case_id_version",
        "case_snapshots",
        ["case_id", "version"],
    )
    op.create_index("ix_case_snapshots_case_version", "case_snapshots", ["case_id", "version"])


def downgrade() -> None:
    op.drop_index("ix_case_snapshots_case_version", table_name="case_snapshots")
    op.drop_constraint("uq_case_snapshots_case_id_version", "case_snapshots", type_="unique")
    op.drop_table("case_snapshots")
