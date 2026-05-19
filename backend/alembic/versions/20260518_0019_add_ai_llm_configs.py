"""add ai_llm_configs table and project.ai_llm_config_id

Revision ID: 20260518_0019
Revises: 20260518_0018
Create Date: 2026-05-18 11:00:00
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "20260518_0019"
down_revision: Union[str, None] = "20260518_0018"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "ai_llm_configs",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("name", sa.String(length=64), nullable=False),
        sa.Column("provider", sa.String(length=32), nullable=False),
        sa.Column("api_key_encrypted", sa.Text(), nullable=False),
        sa.Column("endpoint", sa.String(length=256), nullable=True),
        sa.Column("model_name", sa.String(length=64), nullable=False),
        sa.Column(
            "default_params",
            sa.JSON(),
            nullable=False,
            server_default=sa.text("'{}'"),
        ),
        sa.Column(
            "enabled",
            sa.Boolean(),
            nullable=False,
            server_default=sa.true(),
        ),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.UniqueConstraint("name", name="uq_ai_llm_configs_name"),
    )
    op.create_index(
        "ix_ai_llm_configs_enabled",
        "ai_llm_configs",
        ["enabled"],
    )

    op.add_column(
        "projects",
        sa.Column(
            "ai_llm_config_id",
            sa.Integer(),
            sa.ForeignKey("ai_llm_configs.id"),
            nullable=True,
        ),
    )


def downgrade() -> None:
    op.drop_column("projects", "ai_llm_config_id")
    op.drop_index("ix_ai_llm_configs_enabled", table_name="ai_llm_configs")
    op.drop_table("ai_llm_configs")
