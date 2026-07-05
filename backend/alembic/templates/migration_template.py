"""Migration template for ATP schema changes.

Copy the relevant block(s) into a new revision and remove unused examples.
Every upgrade operation should have a matching downgrade operation unless the
revision explicitly documents why downgrade is unsafe.
"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = "YYYYMMDD_NNNN"
down_revision: Union[str, None] = "PREVIOUS_REVISION"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


# Enum template: define once at module scope and use checkfirst for create/drop.
example_status_enum = sa.Enum(
    "pending",
    "running",
    "passed",
    "failed",
    "error",
    name="example_status",
)


def upgrade() -> None:
    # Enum create: always use checkfirst for PostgreSQL safety.
    example_status_enum.create(op.get_bind(), checkfirst=True)

    op.create_table(
        "example_records",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("project_id", sa.Integer(), nullable=False),
        sa.Column("status", example_status_enum, nullable=False, server_default="pending"),
        sa.Column("name", sa.String(length=128), nullable=False),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"], ondelete="CASCADE"),
        sa.UniqueConstraint("project_id", "name", name="uq_example_records_project_name"),
    )

    # Index names should be explicit and include table + lookup shape.
    op.create_index(
        "ix_example_records_project_status",
        "example_records",
        ["project_id", "status"],
    )


def downgrade() -> None:
    # Drop in reverse dependency order.
    op.drop_index("ix_example_records_project_status", table_name="example_records")
    op.drop_table("example_records")

    # Enum drop: after all dependent columns/tables are gone.
    example_status_enum.drop(op.get_bind(), checkfirst=True)
