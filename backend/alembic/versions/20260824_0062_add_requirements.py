"""Add requirements and requirement-to-case traceability."""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "20260824_0062"
down_revision: Union[str, None] = "20260824_0061"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "test_requirements",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("project_id", sa.Integer(), nullable=False),
        sa.Column("requirement_code", sa.String(length=64), nullable=True),
        sa.Column("title", sa.String(length=256), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("status", sa.String(length=16), nullable=False, server_default="draft"),
        sa.Column("priority", sa.String(length=8), nullable=False, server_default="P2"),
        sa.Column("acceptance_criteria", sa.JSON(), nullable=False, server_default="[]"),
        sa.Column("source", sa.String(length=32), nullable=False, server_default="manual"),
        sa.Column("source_ref", sa.String(length=512), nullable=True),
        sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("creator_id", sa.Integer(), nullable=False),
        sa.Column("owner_id", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["creator_id"], ["users.id"]),
        sa.ForeignKeyConstraint(["owner_id"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("project_id", "requirement_code", name="uq_test_requirements_project_code"),
    )
    op.create_index(
        "ix_test_requirements_project_status",
        "test_requirements",
        ["project_id", "status"],
    )
    op.create_index(
        "ix_test_requirements_project_updated",
        "test_requirements",
        ["project_id", "updated_at"],
    )

    op.create_table(
        "requirement_case_links",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("requirement_id", sa.Integer(), nullable=False),
        sa.Column("case_id", sa.Integer(), nullable=False),
        sa.Column("relation_type", sa.String(length=32), nullable=False, server_default="covers"),
        sa.Column("criterion_ids", sa.JSON(), nullable=False, server_default="[]"),
        sa.Column("note", sa.Text(), nullable=True),
        sa.Column("created_by", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["requirement_id"], ["test_requirements.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["case_id"], ["test_cases.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["created_by"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "requirement_id",
            "case_id",
            "relation_type",
            name="uq_requirement_case_links_relation",
        ),
    )
    op.create_index(
        "ix_requirement_case_links_requirement",
        "requirement_case_links",
        ["requirement_id"],
    )
    op.create_index(
        "ix_requirement_case_links_case",
        "requirement_case_links",
        ["case_id"],
    )


def downgrade() -> None:
    op.drop_index("ix_requirement_case_links_case", table_name="requirement_case_links")
    op.drop_index("ix_requirement_case_links_requirement", table_name="requirement_case_links")
    op.drop_table("requirement_case_links")
    op.drop_index("ix_test_requirements_project_updated", table_name="test_requirements")
    op.drop_index("ix_test_requirements_project_status", table_name="test_requirements")
    op.drop_table("test_requirements")
