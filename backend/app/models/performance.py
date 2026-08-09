"""HTTP performance testing models."""

from __future__ import annotations

import enum
from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Index, Integer, JSON, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin


class PerformanceRunStatus(str, enum.Enum):
    pending = "pending"
    running = "running"
    cancelling = "cancelling"
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

    # 回归比较基线：由 API 校验只能指向本测试的一次成功运行。
    baseline_run_id: Mapped[int | None] = mapped_column(
        ForeignKey("performance_runs.id", ondelete="SET NULL"), nullable=True
    )

    # 定时执行配置默认关闭，避免历史压测定义在迁移后被意外触发。
    schedule_enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    cron_expression: Mapped[str | None] = mapped_column(String(128), nullable=True)
    schedule_timezone: Mapped[str] = mapped_column(String(64), nullable=False, default="Asia/Shanghai")
    schedule_environment_id: Mapped[int | None] = mapped_column(
        ForeignKey("environments.id", ondelete="SET NULL"), nullable=True
    )
    schedule_node_id: Mapped[int | None] = mapped_column(
        ForeignKey("performance_nodes.id", ondelete="SET NULL"), nullable=True
    )
    dataset_id: Mapped[int | None] = mapped_column(ForeignKey("test_datasets.id", ondelete="SET NULL"), nullable=True)
    schedule_options: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    last_scheduled_run_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    next_run_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    project = relationship("Project")
    runs: Mapped[list["PerformanceRun"]] = relationship(
        back_populates="test",
        cascade="all, delete-orphan",
        foreign_keys="PerformanceRun.performance_test_id",
    )


class PerformanceRun(Base, TimestampMixin):
    __tablename__ = "performance_runs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    performance_test_id: Mapped[int] = mapped_column(
        ForeignKey("performance_tests.id", ondelete="CASCADE"), nullable=False
    )
    project_id: Mapped[int] = mapped_column(ForeignKey("projects.id", ondelete="CASCADE"), nullable=False)
    environment_id: Mapped[int | None] = mapped_column(ForeignKey("environments.id", ondelete="SET NULL"))
    performance_node_id: Mapped[int | None] = mapped_column(
        ForeignKey("performance_nodes.id", ondelete="SET NULL"), nullable=True
    )
    parent_run_id: Mapped[int | None] = mapped_column(
        ForeignKey("performance_runs.id", ondelete="CASCADE"), nullable=True, index=True
    )
    dataset_id: Mapped[int | None] = mapped_column(ForeignKey("test_datasets.id", ondelete="SET NULL"), nullable=True)
    dataset_version: Mapped[int | None] = mapped_column(Integer, nullable=True)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default=PerformanceRunStatus.pending.value)
    triggered_by: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    duration_ms: Mapped[int | None] = mapped_column(Integer)
    options_snapshot: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    summary: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    raw_result_object_name: Mapped[str | None] = mapped_column(String(512))
    error_message: Mapped[str | None] = mapped_column(Text)

    test: Mapped["PerformanceTest"] = relationship(
        back_populates="runs",
        foreign_keys=[performance_test_id],
    )
    project = relationship("Project")
    performance_node = relationship("PerformanceNode", back_populates="runs", foreign_keys=[performance_node_id])
    parent_run: Mapped["PerformanceRun | None"] = relationship(
        "PerformanceRun",
        remote_side="PerformanceRun.id",
        back_populates="shard_runs",
        foreign_keys=[parent_run_id],
    )
    shard_runs: Mapped[list["PerformanceRun"]] = relationship(
        "PerformanceRun",
        back_populates="parent_run",
        foreign_keys=[parent_run_id],
        cascade="all, delete-orphan",
    )
    metric_samples: Mapped[list["PerformanceMetricSample"]] = relationship(
        back_populates="run",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )


class PerformanceMetricSample(Base):
    """Resource metrics captured by the worker while a performance run is active."""

    __tablename__ = "performance_metric_samples"
    __table_args__ = (Index("ix_performance_metric_samples_run_captured", "run_id", "captured_at"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    run_id: Mapped[int] = mapped_column(ForeignKey("performance_runs.id", ondelete="CASCADE"), nullable=False)
    captured_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    node_id: Mapped[str] = mapped_column(String(128), nullable=False, default="unknown")
    source: Mapped[str] = mapped_column(String(64), nullable=False, default="performance-worker")
    metrics: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    errors: Mapped[list] = mapped_column(JSON, nullable=False, default=list)

    run = relationship("PerformanceRun", back_populates="metric_samples")
