import enum
import secrets
from datetime import datetime
from sqlalchemy import String, Text, ForeignKey, JSON, Enum, Integer, Boolean, DateTime
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.models.base import Base, TimestampMixin


class PlanStatus(str, enum.Enum):
    draft = "draft"
    active = "active"
    archived = "archived"


class ScheduleType(str, enum.Enum):
    manual = "manual"
    cron = "cron"
    webhook = "webhook"


class TriggerType(str, enum.Enum):
    manual = "manual"
    cron = "cron"
    webhook = "webhook"


class PlanRunStatus(str, enum.Enum):
    pending = "pending"
    running = "running"
    passed = "passed"
    failed = "failed"
    error = "error"


class TestPlan(Base, TimestampMixin):
    __tablename__ = "test_plans"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(256), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    project_id: Mapped[int] = mapped_column(ForeignKey("projects.id"), nullable=False)
    status: Mapped[PlanStatus] = mapped_column(Enum(PlanStatus), default=PlanStatus.active)
    creator_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)

    # 关联的套件列表
    # 结构: [{"suite_id": 1, "sort": 0}, {"suite_id": 2, "sort": 1}]
    suite_ids: Mapped[list] = mapped_column(JSON, default=list)

    # 调度配置
    schedule_type: Mapped[ScheduleType] = mapped_column(Enum(ScheduleType), default=ScheduleType.manual)
    cron_expression: Mapped[str | None] = mapped_column(String(128))
    webhook_secret: Mapped[str | None] = mapped_column(String(64))
    is_enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    auto_create_bugs: Mapped[bool] = mapped_column(Boolean, default=False)

    # 环境配置
    env_id: Mapped[int | None] = mapped_column(ForeignKey("environments.id"))

    # 执行配置（与 TestSuite.config 一致风格）
    # 结构: {"execution_mode": "sequential" | "parallel",
    #         "max_workers": 3,
    #         "fail_strategy": "fast-fail" | "continue" | "require-minimum-pass-rate",
    #         "min_pass_rate": 0.8}
    config: Mapped[dict] = mapped_column(JSON, default=dict)

    # 调度元数据
    last_run_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    next_run_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    project: Mapped["Project"] = relationship()  # noqa: F821
    runs: Mapped[list["PlanRun"]] = relationship(back_populates="plan", cascade="all, delete-orphan")

    def generate_webhook_secret(self):
        self.webhook_secret = secrets.token_urlsafe(32)


class PlanRun(Base, TimestampMixin):
    __tablename__ = "plan_runs"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    plan_id: Mapped[int] = mapped_column(ForeignKey("test_plans.id"), nullable=False)
    triggered_by: Mapped[int | None] = mapped_column(ForeignKey("users.id"))
    trace_id: Mapped[str | None] = mapped_column(String(64), index=True)
    trigger_type: Mapped[TriggerType] = mapped_column(Enum(TriggerType), default=TriggerType.manual)
    status: Mapped[PlanRunStatus] = mapped_column(Enum(PlanRunStatus), default=PlanRunStatus.pending)
    duration_ms: Mapped[int | None] = mapped_column(Integer)
    error_message: Mapped[str | None] = mapped_column(Text)

    # 各套件的执行记录
    # [{"suite_id": 1, "suite_run_id": 101, "status": "passed"}, ...]
    suite_run_ids: Mapped[list] = mapped_column(JSON, default=list)

    # 结果摘要: {"total": 3, "passed": 2, "failed": 1, "error": 0}
    result_summary: Mapped[dict] = mapped_column(JSON, default=dict)

    plan: Mapped["TestPlan"] = relationship(back_populates="runs")
