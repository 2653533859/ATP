"""add reusable Provider/Consumer API contract assets

Revision ID: 20260807_0052
Revises: 20260807_0051
"""

from alembic import op
import sqlalchemy as sa


revision = "20260807_0052"
down_revision = "20260807_0051"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "api_contract_assets",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("project_id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(length=128), nullable=False),
        sa.Column("role", sa.String(length=16), nullable=False),
        sa.Column("format", sa.String(length=16), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("definition", sa.JSON(), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("owner_id", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["owner_id"], ["users.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("project_id", "role", "name", name="uq_api_contract_assets_project_role_name"),
    )


def downgrade() -> None:
    op.drop_table("api_contract_assets")
