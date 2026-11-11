"""add android agent terminal assertions

Revision ID: 20261111_0089
Revises: 20261111_0088
Create Date: 2026-11-11 14:30:00
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "20261111_0089"
down_revision: Union[str, None] = "20261111_0088"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _has_column(table: str, column: str) -> bool:
    inspector = sa.inspect(op.get_bind())
    if not inspector.has_table(table):
        return False
    return column in {item["name"] for item in inspector.get_columns(table)}


def upgrade() -> None:
    # 用户确认的终态断言：模型不能定义成功，草稿只能从这里取回放依据
    if not _has_column("android_agent_sessions", "terminal_assertions"):
        op.add_column(
            "android_agent_sessions",
            sa.Column("terminal_assertions", sa.JSON(), nullable=False, server_default="[]"),
        )


def downgrade() -> None:
    if _has_column("android_agent_sessions", "terminal_assertions"):
        op.drop_column("android_agent_sessions", "terminal_assertions")
