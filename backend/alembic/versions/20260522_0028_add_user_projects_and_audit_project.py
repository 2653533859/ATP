"""P3.C 多租户隔离：user_projects N:N 表 + audit_logs.project_id

Revision ID: 20260522_0028
Revises: 20260521_0027
Create Date: 2026-05-22 10:00:00
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = "20260522_0028"
down_revision: Union[str, None] = "20260521_0027"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


project_role_enum = sa.Enum("owner", "editor", "viewer", name="projectrole")


def upgrade() -> None:
    project_role_enum.create(op.get_bind(), checkfirst=True)

    op.create_table(
        "user_projects",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("user_id", sa.Integer, sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("project_id", sa.Integer, sa.ForeignKey("projects.id", ondelete="CASCADE"), nullable=False),
        sa.Column("role", project_role_enum, nullable=False, server_default="viewer"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("user_id", "project_id", name="uq_user_projects_user_project"),
    )
    op.create_index("ix_user_projects_user_id", "user_projects", ["user_id"])
    op.create_index("ix_user_projects_project_id", "user_projects", ["project_id"])

    op.add_column("audit_logs", sa.Column("project_id", sa.Integer, nullable=True))
    op.create_index("ix_audit_logs_project_id", "audit_logs", ["project_id"])


def downgrade() -> None:
    op.drop_index("ix_audit_logs_project_id", table_name="audit_logs")
    op.drop_column("audit_logs", "project_id")
    op.drop_index("ix_user_projects_project_id", table_name="user_projects")
    op.drop_index("ix_user_projects_user_id", table_name="user_projects")
    op.drop_table("user_projects")
    project_role_enum.drop(op.get_bind(), checkfirst=True)
