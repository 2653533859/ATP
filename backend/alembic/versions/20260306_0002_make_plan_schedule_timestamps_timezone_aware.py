"""make plan schedule timestamps timezone-aware

Revision ID: 20260306_0002
Revises: 20260306_0001
Create Date: 2026-03-06 23:58:00
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = "20260306_0002"
down_revision: Union[str, None] = "20260306_0001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _is_postgresql() -> bool:
    return op.get_bind().dialect.name == "postgresql"


def _column_exists(table_name: str, column_name: str) -> bool:
    result = op.get_bind().execute(
        sa.text(
            """
            SELECT 1
            FROM information_schema.columns
            WHERE table_name = :table_name
              AND column_name = :column_name
            LIMIT 1
            """
        ),
        {"table_name": table_name, "column_name": column_name},
    )
    return result.first() is not None


def upgrade() -> None:
    if not _is_postgresql():
        return

    if _column_exists("test_plans", "last_run_at"):
        op.execute(
            """
            ALTER TABLE test_plans
            ALTER COLUMN last_run_at TYPE TIMESTAMP WITH TIME ZONE
            USING last_run_at AT TIME ZONE 'UTC'
            """
        )
    if _column_exists("test_plans", "next_run_at"):
        op.execute(
            """
            ALTER TABLE test_plans
            ALTER COLUMN next_run_at TYPE TIMESTAMP WITH TIME ZONE
            USING next_run_at AT TIME ZONE 'UTC'
            """
        )


def downgrade() -> None:
    if not _is_postgresql():
        return

    if _column_exists("test_plans", "last_run_at"):
        op.execute(
            """
            ALTER TABLE test_plans
            ALTER COLUMN last_run_at TYPE TIMESTAMP WITHOUT TIME ZONE
            USING last_run_at AT TIME ZONE 'UTC'
            """
        )
    if _column_exists("test_plans", "next_run_at"):
        op.execute(
            """
            ALTER TABLE test_plans
            ALTER COLUMN next_run_at TYPE TIMESTAMP WITHOUT TIME ZONE
            USING next_run_at AT TIME ZONE 'UTC'
            """
        )
