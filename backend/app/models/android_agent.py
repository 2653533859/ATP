"""Database models for Android Natural Language Agent sessions, events, commands, drafts and replays."""

from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, JSON, String, Text, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin


class AndroidAgentSession(Base, TimestampMixin):
    """Lifecycle state, budget, and governance metadata for an Android Agent session."""

    __tablename__ = "android_agent_sessions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    project_id: Mapped[int] = mapped_column(ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, index=True)
    device_id: Mapped[int | None] = mapped_column(
        ForeignKey("devices.id", ondelete="SET NULL"), nullable=True, index=True
    )
    created_by: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True
    )
    title: Mapped[str] = mapped_column(String(128), nullable=False, default="Android Agent Session")
    goal: Mapped[str] = mapped_column(Text, nullable=False)
    expected_outcome: Mapped[str] = mapped_column(Text, nullable=False)
    package_name: Mapped[str] = mapped_column(String(128), nullable=False)
    llm_config_id: Mapped[int | None] = mapped_column(
        ForeignKey("ai_llm_configs.id", ondelete="SET NULL"), nullable=True
    )
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="created", index=True)
    controller: Mapped[str] = mapped_column(String(16), nullable=False, default="agent")
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1, server_default="1")
    control_epoch: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    lease_token: Mapped[str | None] = mapped_column(String(64), nullable=True)
    budget_max_steps: Mapped[int] = mapped_column(Integer, nullable=False, default=30, server_default="30")
    budget_max_calls: Mapped[int] = mapped_column(Integer, nullable=False, default=40, server_default="40")
    steps_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    model_calls_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    total_tokens: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    error_code: Mapped[str | None] = mapped_column(String(64), nullable=True)
    context_values: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    events: Mapped[list[AndroidAgentEvent]] = relationship(
        "AndroidAgentEvent", cascade="all, delete-orphan", passive_deletes=True
    )
    commands: Mapped[list[AndroidAgentCommand]] = relationship(
        "AndroidAgentCommand", cascade="all, delete-orphan", passive_deletes=True
    )


class AndroidAgentEvent(Base):
    """Immutable sequence of observations, decisions, and execution outcomes."""

    __tablename__ = "android_agent_events"
    __table_args__ = (UniqueConstraint("session_id", "seq", name="uq_android_agent_events_session_seq"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    session_id: Mapped[int] = mapped_column(
        ForeignKey("android_agent_sessions.id", ondelete="CASCADE"), nullable=False, index=True
    )
    seq: Mapped[int] = mapped_column(Integer, nullable=False)
    event_type: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    payload: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    artifact_refs: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class AndroidAgentCommand(Base):
    """Physical device commands dispatched under the device write gate with idempotency."""

    __tablename__ = "android_agent_commands"
    __table_args__ = (
        UniqueConstraint("session_id", "idempotency_key", name="uq_android_agent_commands_session_idempotency"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    session_id: Mapped[int] = mapped_column(
        ForeignKey("android_agent_sessions.id", ondelete="CASCADE"), nullable=False, index=True
    )
    seq: Mapped[int] = mapped_column(Integer, nullable=False)
    control_epoch: Mapped[int] = mapped_column(Integer, nullable=False)
    observation_id: Mapped[str] = mapped_column(String(64), nullable=False)
    idempotency_key: Mapped[str] = mapped_column(String(64), nullable=False)
    action: Mapped[str] = mapped_column(String(32), nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="prepared")
    params: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    error_message: Mapped[str | None] = mapped_column(String(256), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class AndroidAgentDraft(Base, TimestampMixin):
    """不可变的低代码草稿版本：编辑只产生新版本，旧版本内容不再变化。"""

    __tablename__ = "android_agent_drafts"
    __table_args__ = (
        UniqueConstraint("session_id", "version", name="uq_android_agent_drafts_session_version"),
        UniqueConstraint("session_id", "content_hash", name="uq_android_agent_drafts_session_hash"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    project_id: Mapped[int] = mapped_column(ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, index=True)
    session_id: Mapped[int] = mapped_column(
        ForeignKey("android_agent_sessions.id", ondelete="CASCADE"), nullable=False, index=True
    )
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    schema_version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="replayable", index=True)
    content_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    steps: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    assertions: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    variables: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    preconditions: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    blocking_issues: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    source_map: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    environment_snapshot: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    created_by: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    published_case_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    replays: Mapped[list[AndroidAgentReplay]] = relationship(
        "AndroidAgentReplay", cascade="all, delete-orphan", passive_deletes=True
    )


class AndroidAgentReplay(Base, TimestampMixin):
    """草稿固定快照的独立回放结果。

    回放复用现有低代码执行器执行，Agent 决策关闭；不请模型临时修复失败步骤。
    """

    __tablename__ = "android_agent_replays"
    __table_args__ = (
        UniqueConstraint("draft_id", "idempotency_key", name="uq_android_agent_replays_draft_idempotency"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    project_id: Mapped[int] = mapped_column(ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, index=True)
    session_id: Mapped[int] = mapped_column(
        ForeignKey("android_agent_sessions.id", ondelete="CASCADE"), nullable=False, index=True
    )
    draft_id: Mapped[int] = mapped_column(
        ForeignKey("android_agent_drafts.id", ondelete="CASCADE"), nullable=False, index=True
    )
    draft_version: Mapped[int] = mapped_column(Integer, nullable=False)
    content_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    idempotency_key: Mapped[str] = mapped_column(String(128), nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="queued", index=True)
    initial_state_confirmed: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    module_id: Mapped[int | None] = mapped_column(ForeignKey("modules.id", ondelete="SET NULL"), nullable=True)
    case_id: Mapped[int | None] = mapped_column(
        ForeignKey("test_cases.id", ondelete="SET NULL"), nullable=True, index=True
    )
    run_id: Mapped[int | None] = mapped_column(
        ForeignKey("test_runs.id", ondelete="SET NULL"), nullable=True, index=True
    )
    environment_snapshot: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    evidence: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    error_code: Mapped[str | None] = mapped_column(String(64), nullable=True)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
