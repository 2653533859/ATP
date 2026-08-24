"""Add encrypted configuration revision history."""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "20260824_0064"
down_revision: Union[str, None] = "20260824_0063"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "configuration_revisions",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("domain", sa.String(length=32), nullable=False),
        sa.Column("resource_id", sa.Integer(), nullable=False),
        sa.Column("project_id", sa.Integer(), nullable=True),
        sa.Column("resource_name", sa.String(length=256), nullable=False),
        sa.Column("payload_encrypted", sa.Text(), nullable=False),
        sa.Column("redacted_payload", sa.JSON(), nullable=False, server_default="{}"),
        sa.Column("fingerprint", sa.String(length=64), nullable=False),
        sa.Column("reason", sa.String(length=512), nullable=True),
        sa.Column("created_by", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["created_by"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_configuration_revisions_domain_resource_created",
        "configuration_revisions",
        ["domain", "resource_id", "created_at"],
    )
    op.create_index(
        "ix_configuration_revisions_project_created",
        "configuration_revisions",
        ["project_id", "created_at"],
    )
    op.create_index("ix_configuration_revisions_fingerprint", "configuration_revisions", ["fingerprint"])


def downgrade() -> None:
    op.drop_index("ix_configuration_revisions_fingerprint", table_name="configuration_revisions")
    op.drop_index("ix_configuration_revisions_project_created", table_name="configuration_revisions")
    op.drop_index("ix_configuration_revisions_domain_resource_created", table_name="configuration_revisions")
    op.drop_table("configuration_revisions")
