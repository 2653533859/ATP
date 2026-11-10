"""add android agent sessions events and commands tables

Revision ID: 20261110_0086
Revises: 20261104_0085
Create Date: 2026-11-10 10:00:00
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "20261110_0086"
down_revision: Union[str, None] = "20261104_0085"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _has_table(name: str) -> bool:
    return sa.inspect(op.get_bind()).has_table(name)


def upgrade() -> None:
    if not _has_table("android_agent_sessions"):
        op.create_table(
            "android_agent_sessions",
            sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
            sa.Column("project_id", sa.Integer(), nullable=False),
            sa.Column("device_id", sa.Integer(), nullable=True),
            sa.Column("created_by", sa.Integer(), nullable=True),
            sa.Column("title", sa.String(length=128), server_default="Android Agent Session", nullable=False),
            sa.Column("goal", sa.Text(), nullable=False),
            sa.Column("expected_outcome", sa.Text(), nullable=False),
            sa.Column("package_name", sa.String(length=128), nullable=False),
            sa.Column("llm_config_id", sa.Integer(), nullable=True),
            sa.Column("status", sa.String(length=32), server_default="created", nullable=False),
            sa.Column("controller", sa.String(length=16), server_default="agent", nullable=False),
            sa.Column("version", sa.Integer(), server_default="1", nullable=False),
            sa.Column("control_epoch", sa.Integer(), server_default="0", nullable=False),
            sa.Column("lease_token", sa.String(length=64), nullable=True),
            sa.Column("budget_max_steps", sa.Integer(), server_default="30", nullable=False),
            sa.Column("budget_max_calls", sa.Integer(), server_default="40", nullable=False),
            sa.Column("steps_count", sa.Integer(), server_default="0", nullable=False),
            sa.Column("model_calls_count", sa.Integer(), server_default="0", nullable=False),
            sa.Column("total_tokens", sa.Integer(), server_default="0", nullable=False),
            sa.Column("error_code", sa.String(length=64), nullable=True),
            sa.Column("context_values", sa.JSON(), server_default="{}", nullable=False),
            sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
            sa.ForeignKeyConstraint(["created_by"], ["users.id"], ondelete="SET NULL"),
            sa.ForeignKeyConstraint(["device_id"], ["devices.id"], ondelete="SET NULL"),
            sa.ForeignKeyConstraint(["llm_config_id"], ["ai_llm_configs.id"], ondelete="SET NULL"),
            sa.ForeignKeyConstraint(["project_id"], ["projects.id"], ondelete="CASCADE"),
            sa.PrimaryKeyConstraint("id"),
        )
        op.create_index("ix_android_agent_sessions_project_id", "android_agent_sessions", ["project_id"])
        op.create_index("ix_android_agent_sessions_device_id", "android_agent_sessions", ["device_id"])
        op.create_index("ix_android_agent_sessions_status", "android_agent_sessions", ["status"])

    if not _has_table("android_agent_events"):
        op.create_table(
            "android_agent_events",
            sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
            sa.Column("session_id", sa.Integer(), nullable=False),
            sa.Column("seq", sa.Integer(), nullable=False),
            sa.Column("event_type", sa.String(length=32), nullable=False),
            sa.Column("payload", sa.JSON(), server_default="{}", nullable=False),
            sa.Column("artifact_refs", sa.JSON(), server_default="[]", nullable=False),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
            sa.ForeignKeyConstraint(["session_id"], ["android_agent_sessions.id"], ondelete="CASCADE"),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint("session_id", "seq", name="uq_android_agent_events_session_seq"),
        )
        op.create_index("ix_android_agent_events_session_id", "android_agent_events", ["session_id"])
        op.create_index("ix_android_agent_events_event_type", "android_agent_events", ["event_type"])

    if not _has_table("android_agent_commands"):
        op.create_table(
            "android_agent_commands",
            sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
            sa.Column("session_id", sa.Integer(), nullable=False),
            sa.Column("seq", sa.Integer(), nullable=False),
            sa.Column("control_epoch", sa.Integer(), nullable=False),
            sa.Column("observation_id", sa.String(length=64), nullable=False),
            sa.Column("idempotency_key", sa.String(length=64), nullable=False),
            sa.Column("action", sa.String(length=32), nullable=False),
            sa.Column("status", sa.String(length=32), server_default="prepared", nullable=False),
            sa.Column("params", sa.JSON(), server_default="{}", nullable=False),
            sa.Column("error_message", sa.String(length=256), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
            sa.ForeignKeyConstraint(["session_id"], ["android_agent_sessions.id"], ondelete="CASCADE"),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint("session_id", "idempotency_key", name="uq_android_agent_commands_session_idempotency"),
        )
        op.create_index("ix_android_agent_commands_session_id", "android_agent_commands", ["session_id"])


def downgrade() -> None:
    if _has_table("android_agent_commands"):
        op.drop_index("ix_android_agent_commands_session_id", table_name="android_agent_commands")
        op.drop_table("android_agent_commands")
    if _has_table("android_agent_events"):
        op.drop_index("ix_android_agent_events_event_type", table_name="android_agent_events")
        op.drop_index("ix_android_agent_events_session_id", table_name="android_agent_events")
        op.drop_table("android_agent_events")
    if _has_table("android_agent_sessions"):
        op.drop_index("ix_android_agent_sessions_status", table_name="android_agent_sessions")
        op.drop_index("ix_android_agent_sessions_device_id", table_name="android_agent_sessions")
        op.drop_index("ix_android_agent_sessions_project_id", table_name="android_agent_sessions")
        op.drop_table("android_agent_sessions")
