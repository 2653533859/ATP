"""add notification delivery history

Revision ID: 20260813_0057
Revises: 20260813_0056
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = "20260813_0057"
down_revision: Union[str, None] = "20260813_0056"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


notify_channel_enum = postgresql.ENUM(
    "email",
    "wechat",
    "dingtalk",
    name="notifychannel",
    create_type=False,
)


def upgrade() -> None:
    op.create_table(
        "notification_deliveries",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("project_id", sa.Integer(), sa.ForeignKey("projects.id", ondelete="CASCADE"), nullable=False),
        sa.Column(
            "notification_config_id",
            sa.Integer(),
            sa.ForeignKey("notification_configs.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("channel", notify_channel_enum, nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("attempts", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("summary", sa.JSON(), nullable=False, server_default=sa.text("'{}'")),
        sa.Column("error_message", sa.String(length=1000), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_notification_deliveries_project_id", "notification_deliveries", ["project_id"])
    op.create_index("ix_notification_deliveries_notification_config_id", "notification_deliveries", ["notification_config_id"])
    op.create_index("ix_notification_deliveries_status", "notification_deliveries", ["status"])


def downgrade() -> None:
    op.drop_index("ix_notification_deliveries_status", table_name="notification_deliveries")
    op.drop_index("ix_notification_deliveries_notification_config_id", table_name="notification_deliveries")
    op.drop_index("ix_notification_deliveries_project_id", table_name="notification_deliveries")
    op.drop_table("notification_deliveries")
