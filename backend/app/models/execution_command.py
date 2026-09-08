"""Persistent idempotency ledger for unified execution commands."""

from __future__ import annotations

from sqlalchemy import ForeignKey, Index, Integer, JSON, String, Text, UniqueConstraint, text
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin


class ExecutionCommand(Base, TimestampMixin):
    """Record one user-issued retry or stop command and its durable result."""

    __tablename__ = "execution_commands"
    __table_args__ = (
        UniqueConstraint("user_id", "command_id", name="uq_execution_commands_user_command"),
        Index(
            "uq_execution_commands_target_action",
            "action",
            "task_type",
            "run_id",
            unique=True,
            postgresql_where=text("status IN ('processing', 'succeeded', 'indeterminate')"),
            sqlite_where=text("status IN ('processing', 'succeeded', 'indeterminate')"),
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    command_id: Mapped[str] = mapped_column(String(128), nullable=False)
    action: Mapped[str] = mapped_column(String(16), nullable=False)
    task_type: Mapped[str] = mapped_column(String(32), nullable=False)
    run_id: Mapped[int] = mapped_column(Integer, nullable=False)
    project_id: Mapped[int | None] = mapped_column(
        ForeignKey("projects.id", ondelete="SET NULL"), nullable=True, index=True
    )
    source_status: Mapped[str] = mapped_column(String(32), nullable=False)
    result_status: Mapped[str | None] = mapped_column(String(32), nullable=True)
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="processing")
    response_json: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    error_status_code: Mapped[int | None] = mapped_column(Integer, nullable=True)
    error_detail: Mapped[str | None] = mapped_column(Text, nullable=True)
