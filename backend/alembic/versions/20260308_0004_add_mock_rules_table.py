"""add mock_rules table

Revision ID: 20260308_0004
Revises: 20260307_0003
Create Date: 2026-03-08 10:00:00
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = "20260308_0004"
down_revision: Union[str, None] = "20260307_0003"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


mock_method_enum = postgresql.ENUM(
    "GET",
    "POST",
    "PUT",
    "DELETE",
    "PATCH",
    "ANY",
    name="mockmethod",
    create_type=False,
)


def upgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        mock_method_enum.create(bind, checkfirst=True)

    op.create_table(
        "mock_rules",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("name", sa.String(length=128), nullable=False),
        sa.Column("project_id", sa.Integer(), sa.ForeignKey("projects.id", ondelete="CASCADE"), nullable=False),
        sa.Column("method", mock_method_enum, nullable=False),
        sa.Column("path", sa.String(length=512), nullable=False),
        sa.Column("status_code", sa.Integer(), nullable=False, server_default="200"),
        sa.Column("response_headers", sa.JSON(), nullable=False, server_default=sa.text("'{}'")),
        sa.Column("response_body", sa.Text(), nullable=True),
        sa.Column("delay_ms", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("is_enabled", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("creator_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )


def downgrade() -> None:
    op.drop_table("mock_rules")
    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        mock_method_enum.drop(bind, checkfirst=True)
