"""add Web visual regression baselines

Revision ID: 20260807_0050
Revises: 20260807_0049
"""

from alembic import op
import sqlalchemy as sa


revision = "20260807_0050"
down_revision = "20260807_0049"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "web_visual_baselines",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("project_id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(length=128), nullable=False),
        sa.Column("page_url", sa.String(length=512), nullable=True),
        sa.Column("object_name", sa.String(length=512), nullable=False),
        sa.Column("content_type", sa.String(length=128), nullable=False),
        sa.Column("width", sa.Integer(), nullable=True),
        sa.Column("height", sa.Integer(), nullable=True),
        sa.Column("threshold", sa.Float(), nullable=False),
        sa.Column("pixel_threshold", sa.Integer(), nullable=False),
        sa.Column("ignore_regions", sa.JSON(), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("owner_id", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["owner_id"], ["users.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("project_id", "name", name="uq_web_visual_baselines_project_name"),
    )
    op.create_index("ix_web_visual_baselines_project_page", "web_visual_baselines", ["project_id", "page_url"])


def downgrade() -> None:
    op.drop_index("ix_web_visual_baselines_project_page", table_name="web_visual_baselines")
    op.drop_table("web_visual_baselines")
