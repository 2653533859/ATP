"""HTTP performance testing models."""

from __future__ import annotations

import enum
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, JSON, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin


class PerformanceRunStatus(str, enum.Enum):
    pending = "pending"
    running = "running"
    success = "success"
    failed = "failed"
    cancelled = "cancelled"


class PerformanceTest(Base, TimestampMixin):
    __tablename__ = "performance_tests"
    __table_args__ = (UniqueConstraint("project_id", "name", name="uq_performance_tests_project_name"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    project_id: Mapped[int] = mapped_column(ForeignKey("projects.id", ondelete="CASCADE"), nullable=False)
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    executor: Mapped[str] = mapped_column(String(32), nullable=False, default="k6")
    script_object_name: Mapped[str] = mapped_column(String(512), nullable=False)
    default_options: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    creator_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)

    project = relationship("Project")
    runs: Mapped[list["PerformanceRun"]] = relationship(
        back_populates="test",
        cascade="all, delete-orphan",
    )


class PerformanceRun(Base, TimestampMixin):
    __tablename__ = "performance_runs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    performance_test_id: Mapped[int] = mapped_column(
        ForeignKey("performance_tests.id", ondelete="CASCADE"), nullable=False
    )
    project_id: Mapped[int] = mapped_column(ForeignKey("projects.id", ondelete="CASCADE"), nullable=False)
    environment_id: Mapped[int | None] = mapped_column(ForeignKey("environments.id", ondelete="SET NULL"))
    status: Mapped[str] = mapped_column(String(32), nullable=False, default=PerformanceRunStatus.pending.value)
    triggered_by: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    duration_ms: Mapped[int | None] = mapped_column(Integer)
    options_snapshot: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    summary: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    raw_result_object_name: Mapped[str | None] = mapped_column(String(512))
    error_message: Mapped[str | None] = mapped_column(Text)

    test: Mapped["PerformanceTest"] = relationship(back_populates="runs")
    project = relationship("Project")
