"""Durable cooperative group cancellation and child ownership.

Revision ID: 20261008_0079
Revises: 20261008_0078
"""

from alembic import op
import sqlalchemy as sa
from uuid import uuid4

revision: str = "20261008_0079"
down_revision: str = "20261008_0078"
branch_labels: str | None = None
depends_on: str | None = None


def upgrade() -> None:
    op.add_column("suite_runs", sa.Column("cancel_requested_at", sa.DateTime(timezone=True)))
    op.add_column("plan_runs", sa.Column("cancel_requested_at", sa.DateTime(timezone=True)))
    connection = op.get_bind()
    identity_default = sa.text("replace(gen_random_uuid()::text, '-', '')") if connection.dialect.name == "postgresql" else None
    op.add_column("plan_runs", sa.Column("identity_token", sa.String(32), nullable=True, server_default=identity_default))
    table = sa.table("plan_runs", sa.column("id", sa.Integer), sa.column("identity_token", sa.String(32)))
    last_id = -1
    while True:
        ids = connection.execute(sa.select(table.c.id).where(table.c.id > last_id, table.c.identity_token.is_(None))
                                 .order_by(table.c.id).limit(1000)).scalars().all()
        if not ids:
            break
        for resource_id in ids:
            connection.execute(table.update().where(table.c.id == resource_id).values(identity_token=uuid4().hex))
        last_id = ids[-1]
    with op.batch_alter_table("plan_runs") as batch:
        batch.alter_column("identity_token", existing_type=sa.String(32), nullable=False)
    op.create_table(
        "group_run_children",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("parent_kind", sa.String(16), nullable=False),
        sa.Column("parent_run_id", sa.Integer(), nullable=False),
        sa.Column("parent_identity", sa.String(32), nullable=False),
        sa.Column("child_kind", sa.String(16), nullable=False),
        sa.Column("child_id", sa.Integer(), nullable=False),
        sa.Column("child_identity", sa.String(128), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("parent_kind", "parent_identity", "child_id", "child_identity",
                            name="uq_group_run_children_identity"),
    )
    op.create_index("ix_group_run_children_parent_identity", "group_run_children", ["parent_identity"])


def downgrade() -> None:
    op.drop_index("ix_group_run_children_parent_identity", table_name="group_run_children")
    op.drop_table("group_run_children")
    op.drop_column("plan_runs", "identity_token")
    op.drop_column("plan_runs", "cancel_requested_at")
    op.drop_column("suite_runs", "cancel_requested_at")
