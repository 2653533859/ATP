"""Q6 P1.1: add dashboard alert rules and events

Revision ID: 20260527_0030
Revises: 20260525_0029
Create Date: 2026-05-27 20:00:00
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql


revision: str = "20260527_0030"
down_revision: Union[str, None] = "20260525_0029"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


metric_enum = postgresql.ENUM(
    "pass_rate",
    "avg_duration_ms",
    "failure_count",
    "error_count",
    "total_runs",
    name="dashboardalertmetric",
    create_type=False,
)
operator_enum = postgresql.ENUM("gt", "gte", "lt", "lte", "eq", name="dashboardalertoperator", create_type=False)


def upgrade() -> None:
    metric_enum.create(op.get_bind(), checkfirst=True)
    operator_enum.create(op.get_bind(), checkfirst=True)

    op.create_table(
        "dashboard_alert_rules",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("name", sa.String(length=128), nullable=False),
        sa.Column("project_id", sa.Integer(), nullable=False),
        sa.Column("metric", metric_enum, nullable=False),
        sa.Column("op", operator_enum, nullable=False),
        sa.Column("threshold", sa.Float(), nullable=False),
        sa.Column("window_minutes", sa.Integer(), nullable=False),
        sa.Column("suppress_minutes", sa.Integer(), nullable=False),
        sa.Column("notification_config_id", sa.Integer(), nullable=True),
        sa.Column("enabled", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["notification_config_id"], ["notification_configs.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_dashboard_alert_rules_project_id", "dashboard_alert_rules", ["project_id"])
    op.create_index(
        "ix_dashboard_alert_rules_project_enabled",
        "dashboard_alert_rules",
        ["project_id", "enabled"],
    )

    op.create_table(
        "dashboard_alert_events",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("rule_id", sa.Integer(), nullable=False),
        sa.Column("triggered_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("actual_value", sa.Float(), nullable=False),
        sa.Column("snoozed_until", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["rule_id"], ["dashboard_alert_rules.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_dashboard_alert_events_rule_triggered", "dashboard_alert_events", ["rule_id", "triggered_at"])


def downgrade() -> None:
    op.drop_index("ix_dashboard_alert_events_rule_triggered", table_name="dashboard_alert_events")
    op.drop_table("dashboard_alert_events")
    op.drop_index("ix_dashboard_alert_rules_project_enabled", table_name="dashboard_alert_rules")
    op.drop_index("ix_dashboard_alert_rules_project_id", table_name="dashboard_alert_rules")
    op.drop_table("dashboard_alert_rules")
    operator_enum.drop(op.get_bind(), checkfirst=True)
    metric_enum.drop(op.get_bind(), checkfirst=True)
