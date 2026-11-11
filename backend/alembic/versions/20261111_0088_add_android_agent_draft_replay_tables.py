"""add android agent draft and replay tables

Revision ID: 20261111_0088
Revises: 20261110_0087
Create Date: 2026-11-11 10:00:00
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "20261111_0088"
down_revision: Union[str, None] = "20261110_0087"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _has_table(name: str) -> bool:
    return sa.inspect(op.get_bind()).has_table(name)


def upgrade() -> None:
    if not _has_table("android_agent_drafts"):
        op.create_table(
            "android_agent_drafts",
            sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
            sa.Column("project_id", sa.Integer(), nullable=False),
            sa.Column("session_id", sa.Integer(), nullable=False),
            sa.Column("version", sa.Integer(), nullable=False),
            sa.Column("schema_version", sa.Integer(), nullable=False),
            sa.Column("status", sa.String(length=32), nullable=False),
            sa.Column("content_hash", sa.String(length=64), nullable=False),
            sa.Column("steps", sa.JSON(), nullable=False),
            sa.Column("assertions", sa.JSON(), nullable=False),
            sa.Column("variables", sa.JSON(), nullable=False),
            sa.Column("preconditions", sa.JSON(), nullable=False),
            sa.Column("blocking_issues", sa.JSON(), nullable=False),
            sa.Column("source_map", sa.JSON(), nullable=False),
            sa.Column("environment_snapshot", sa.JSON(), nullable=False),
            sa.Column("created_by", sa.Integer(), nullable=True),
            sa.Column("published_case_id", sa.Integer(), nullable=True),
            sa.Column("published_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
            sa.ForeignKeyConstraint(["project_id"], ["projects.id"], ondelete="CASCADE"),
            sa.ForeignKeyConstraint(["session_id"], ["android_agent_sessions.id"], ondelete="CASCADE"),
            sa.ForeignKeyConstraint(["created_by"], ["users.id"], ondelete="SET NULL"),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint("session_id", "version", name="uq_android_agent_drafts_session_version"),
            sa.UniqueConstraint("session_id", "content_hash", name="uq_android_agent_drafts_session_hash"),
        )
        op.create_index("ix_android_agent_drafts_project_id", "android_agent_drafts", ["project_id"])
        op.create_index("ix_android_agent_drafts_session_id", "android_agent_drafts", ["session_id"])
        op.create_index("ix_android_agent_drafts_status", "android_agent_drafts", ["status"])

    if not _has_table("android_agent_replays"):
        op.create_table(
            "android_agent_replays",
            sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
            sa.Column("project_id", sa.Integer(), nullable=False),
            sa.Column("session_id", sa.Integer(), nullable=False),
            sa.Column("draft_id", sa.Integer(), nullable=False),
            sa.Column("draft_version", sa.Integer(), nullable=False),
            sa.Column("content_hash", sa.String(length=64), nullable=False),
            sa.Column("idempotency_key", sa.String(length=128), nullable=False),
            sa.Column("status", sa.String(length=32), nullable=False),
            sa.Column("initial_state_confirmed", sa.Boolean(), nullable=False),
            sa.Column("module_id", sa.Integer(), nullable=True),
            sa.Column("case_id", sa.Integer(), nullable=True),
            sa.Column("run_id", sa.Integer(), nullable=True),
            sa.Column("environment_snapshot", sa.JSON(), nullable=False),
            sa.Column("evidence", sa.JSON(), nullable=False),
            sa.Column("error_code", sa.String(length=64), nullable=True),
            sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
            sa.ForeignKeyConstraint(["project_id"], ["projects.id"], ondelete="CASCADE"),
            sa.ForeignKeyConstraint(["session_id"], ["android_agent_sessions.id"], ondelete="CASCADE"),
            sa.ForeignKeyConstraint(["draft_id"], ["android_agent_drafts.id"], ondelete="CASCADE"),
            sa.ForeignKeyConstraint(["module_id"], ["modules.id"], ondelete="SET NULL"),
            sa.ForeignKeyConstraint(["case_id"], ["test_cases.id"], ondelete="SET NULL"),
            sa.ForeignKeyConstraint(["run_id"], ["test_runs.id"], ondelete="SET NULL"),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint("draft_id", "idempotency_key", name="uq_android_agent_replays_draft_idempotency"),
        )
        op.create_index("ix_android_agent_replays_project_id", "android_agent_replays", ["project_id"])
        op.create_index("ix_android_agent_replays_session_id", "android_agent_replays", ["session_id"])
        op.create_index("ix_android_agent_replays_draft_id", "android_agent_replays", ["draft_id"])
        op.create_index("ix_android_agent_replays_status", "android_agent_replays", ["status"])
        op.create_index("ix_android_agent_replays_case_id", "android_agent_replays", ["case_id"])
        op.create_index("ix_android_agent_replays_run_id", "android_agent_replays", ["run_id"])


def downgrade() -> None:
    if _has_table("android_agent_replays"):
        op.drop_table("android_agent_replays")
    if _has_table("android_agent_drafts"):
        op.drop_table("android_agent_drafts")
