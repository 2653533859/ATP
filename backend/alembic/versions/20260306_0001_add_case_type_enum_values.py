"""add graphql/websocket/grpc to case type enum

Revision ID: 20260306_0001
Revises:
Create Date: 2026-03-06 23:40:00
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = "20260306_0001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

NEW_CASE_TYPE_VALUES = ("graphql", "websocket", "grpc")
CANDIDATE_ENUM_NAMES = ("case_type", "casetype")


def _is_postgresql() -> bool:
    return op.get_bind().dialect.name == "postgresql"


def _resolve_case_type_enum_name() -> str | None:
    bind = op.get_bind()
    column_enum_result = bind.execute(
        sa.text(
            """
            SELECT t.typname
            FROM pg_attribute AS a
            JOIN pg_class AS c ON c.oid = a.attrelid
            JOIN pg_type AS t ON t.oid = a.atttypid
            WHERE c.relname = 'test_cases'
              AND a.attname = 'case_type'
              AND a.attnum > 0
              AND NOT a.attisdropped
            LIMIT 1
            """
        )
    )
    column_enum_row = column_enum_result.first()
    if column_enum_row:
        return column_enum_row[0]

    result = bind.execute(
        sa.text(
            """
            SELECT t.typname
            FROM pg_type AS t
            WHERE t.typname = ANY(:enum_names)
            ORDER BY CASE WHEN t.typname = 'case_type' THEN 0 ELSE 1 END
            LIMIT 1
            """
        ),
        {"enum_names": list(CANDIDATE_ENUM_NAMES)},
    )
    row = result.first()
    return row[0] if row else None


def upgrade() -> None:
    if not _is_postgresql():
        return

    enum_name = _resolve_case_type_enum_name()
    if not enum_name:
        return

    quoted_enum_name = op.get_bind().dialect.identifier_preparer.quote(enum_name)
    for enum_value in NEW_CASE_TYPE_VALUES:
        with op.get_context().autocommit_block():
            op.execute(f"ALTER TYPE {quoted_enum_name} ADD VALUE IF NOT EXISTS '{enum_value}'")


def downgrade() -> None:
    # PostgreSQL enum values cannot be safely removed in-place without rebuilding
    # dependent columns and data. Keep downgrade as a no-op.
    pass
