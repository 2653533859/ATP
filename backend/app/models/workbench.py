"""Workbench models for todo silence/snooze and task archiving."""

from __future__ import annotations

from datetime import datetime, timezone
from sqlalchemy import DateTime, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class WorkbenchTodoSnooze(Base):
    """Persisted snooze record for dynamically aggregated workbench todos."""

    __tablename__ = "workbench_todo_snoozes"
    __table_args__ = (UniqueConstraint("user_id", "todo_id", name="uq_workbench_todo_snoozes_user_todo"),)

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    todo_id: Mapped[str] = mapped_column(String(128), index=True, nullable=False)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    project_id: Mapped[int | None] = mapped_column(
        ForeignKey("projects.id", ondelete="CASCADE"), nullable=True, index=True
    )
    reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    snoozed_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True, index=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )


class WorkbenchArchivedTask(Base):
    """Soft archive marker for workbench tasks across execution domains."""

    __tablename__ = "workbench_archived_tasks"
    __table_args__ = (UniqueConstraint("task_type", "run_id", name="uq_workbench_archived_tasks_type_run"),)

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    task_type: Mapped[str] = mapped_column(String(32), nullable=False)
    run_id: Mapped[int] = mapped_column(Integer, nullable=False)
    project_id: Mapped[int | None] = mapped_column(
        ForeignKey("projects.id", ondelete="CASCADE"), nullable=True, index=True
    )
    archived_by: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    archived_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )
