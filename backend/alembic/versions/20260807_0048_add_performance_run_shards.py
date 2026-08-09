"""add parent relation for distributed performance run shards"""

from alembic import op
import sqlalchemy as sa

revision = "20260807_0048"
down_revision = "20260807_0047"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("performance_runs", sa.Column("parent_run_id", sa.Integer(), nullable=True))
    op.create_foreign_key(
        "fk_performance_runs_parent_run_id",
        "performance_runs",
        "performance_runs",
        ["parent_run_id"],
        ["id"],
        ondelete="CASCADE",
    )
    op.create_index("ix_performance_runs_parent_run_id", "performance_runs", ["parent_run_id"])


def downgrade() -> None:
    op.drop_index("ix_performance_runs_parent_run_id", table_name="performance_runs")
    op.drop_constraint("fk_performance_runs_parent_run_id", "performance_runs", type_="foreignkey")
    op.drop_column("performance_runs", "parent_run_id")
