"""Immutable identities for suite command resources.

Revision ID: 20261007_0076
Revises: 20261003_0075
"""

from uuid import uuid4

from alembic import op
import sqlalchemy as sa

revision: str = "20261007_0076"
down_revision: str = "20261003_0075"
branch_labels: str | None = None
depends_on: str | None = None


def upgrade() -> None:
    connection = op.get_bind()
    # PostgreSQL 16 is the repository's deployment/CI baseline. Keep a DB default
    # so old writers during a rolling upgrade also receive fresh identities.
    identity_default = (
        sa.text("replace(gen_random_uuid()::text, '-', '')")
        if connection.dialect.name == "postgresql"
        else None
    )
    for table_name in ("test_suites", "suite_runs"):
        op.add_column(
            table_name,
            sa.Column("identity_token", sa.String(32), server_default=identity_default, nullable=True),
        )
        table = sa.table(table_name, sa.column("id", sa.Integer), sa.column("identity_token", sa.String(32)))
        # Keyset batches avoid buffering a large historical run table.
        last_id = -1
        while True:
            ids = connection.execute(
                sa.select(table.c.id)
                .where(table.c.id > last_id, table.c.identity_token.is_(None))
                .order_by(table.c.id)
                .limit(1000)
            ).scalars().all()
            if not ids:
                break
            for resource_id in ids:
                connection.execute(table.update().where(table.c.id == resource_id).values(identity_token=uuid4().hex))
            last_id = ids[-1]
        with op.batch_alter_table(table_name) as batch:
            batch.alter_column("identity_token", existing_type=sa.String(32), nullable=False)
    # Do not infer old receipt identities from IDs that may already have been reused.
    op.add_column("hermes_actions", sa.Column("resource_identity", sa.String(32), nullable=True))


def downgrade() -> None:
    op.drop_column("hermes_actions", "resource_identity")
    for table_name in ("suite_runs", "test_suites"):
        with op.batch_alter_table(table_name) as batch:
            batch.drop_column("identity_token")
