"""Add the cancelled terminal status for cooperative Web run cancellation."""

from typing import Sequence, Union

from alembic import op

revision: str = "20260909_0072"
down_revision: Union[str, None] = "20260909_0071"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("ALTER TYPE runstatus ADD VALUE IF NOT EXISTS 'cancelled'")


def downgrade() -> None:
    # PostgreSQL cannot remove an enum value without rebuilding every dependent
    # column. Mapping rows keeps older application versions compatible; the
    # unused value may safely remain in the database type.
    op.execute("UPDATE test_runs SET status = 'failed' WHERE status = 'cancelled'")
