"""Permanent execution acceptance for suite dispatches.

Revision ID: 20261008_0078
Revises: 20261008_0077
"""

from alembic import op
import sqlalchemy as sa

revision: str = "20261008_0078"
down_revision: str = "20261008_0077"
branch_labels: str | None = None
depends_on: str | None = None


def upgrade() -> None:
    op.add_column("execution_dispatches", sa.Column("execution_token", sa.String(32)))
    op.add_column("execution_dispatches", sa.Column("accepted_at", sa.DateTime(timezone=True)))
    op.add_column("execution_run_leases", sa.Column("run_identity", sa.String(32)))


def downgrade() -> None:
    # Removing acceptance permits old messages to be accepted again. Stop and
    # drain execution traffic before explicitly downgrading this revision.
    op.drop_column("execution_run_leases", "run_identity")
    op.drop_column("execution_dispatches", "accepted_at")
    op.drop_column("execution_dispatches", "execution_token")
