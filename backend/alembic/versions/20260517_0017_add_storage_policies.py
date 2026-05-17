"""add storage policies table

Revision ID: 20260517_0017
Revises: 20260403_0016
Create Date: 2026-05-17 10:00:00
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "20260517_0017"
down_revision: Union[str, None] = "20260403_0016"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "storage_policies",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("name", sa.String(length=64), nullable=False),
        sa.Column("prefix", sa.String(length=128), nullable=False),
        sa.Column("retention_days", sa.Integer(), nullable=False, server_default="30"),
        sa.Column("max_size_gb", sa.Float(), nullable=True),
        sa.Column("enabled", sa.Boolean(), nullable=False, server_default=sa.true()),
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
        sa.UniqueConstraint("name", name="uq_storage_policies_name"),
        sa.UniqueConstraint("prefix", name="uq_storage_policies_prefix"),
    )
    op.create_index(
        "ix_storage_policies_enabled",
        "storage_policies",
        ["enabled"],
    )

    op.bulk_insert(
        sa.table(
            "storage_policies",
            sa.column("name", sa.String),
            sa.column("prefix", sa.String),
            sa.column("retention_days", sa.Integer),
            sa.column("enabled", sa.Boolean),
            sa.column("description", sa.Text),
        ),
        [
            {
                "name": "screenshots",
                "prefix": "screenshots/",
                "retention_days": 30,
                "enabled": True,
                "description": "执行截图：默认保留 30 天",
            },
            {
                "name": "reports",
                "prefix": "reports/",
                "retention_days": 90,
                "enabled": True,
                "description": "执行报告：默认保留 90 天",
            },
            {
                "name": "apks",
                "prefix": "apks/",
                "retention_days": 180,
                "enabled": True,
                "description": "APK 安装包：默认保留 180 天",
            },
            {
                "name": "scripts",
                "prefix": "scripts/",
                "retention_days": 365,
                "enabled": True,
                "description": "测试脚本：默认保留 365 天",
            },
        ],
    )


def downgrade() -> None:
    op.drop_index("ix_storage_policies_enabled", table_name="storage_policies")
    op.drop_table("storage_policies")
