"""add performance run idempotency keys

Revision ID: 20260813_0056
Revises: 20260812_0055
"""

from alembic import op
import sqlalchemy as sa


revision = "20260813_0056"
down_revision = "20260812_0055"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("performance_runs", sa.Column("idempotency_key", sa.String(length=128), nullable=True))
    op.add_column("performance_runs", sa.Column("idempotency_fingerprint", sa.String(length=64), nullable=True))
    op.create_unique_constraint(
        "uq_performance_runs_idempotency_key",
        "performance_runs",
        ["project_id", "performance_test_id", "idempotency_key"],
    )


def downgrade() -> None:
    op.drop_constraint("uq_performance_runs_idempotency_key", "performance_runs", type_="unique")
    op.drop_column("performance_runs", "idempotency_key")
    op.drop_column("performance_runs", "idempotency_fingerprint")
