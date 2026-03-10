import enum
from datetime import datetime

from sqlalchemy import Boolean, DateTime, Enum, ForeignKey, Integer, JSON, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin
from app.models.project import Module  # noqa: F401


class CaseType(str, enum.Enum):
    api = "api"
    web = "web"
    android = "android"
    graphql = "graphql"
    websocket = "websocket"
    grpc = "grpc"


class CaseStatus(str, enum.Enum):
    draft = "draft"
    active = "active"
    deprecated = "deprecated"


class RunStatus(str, enum.Enum):
    pending = "pending"
    running = "running"
    passed = "passed"
    failed = "failed"
    error = "error"
    skipped = "skipped"


class TestCase(Base, TimestampMixin):
    __tablename__ = "test_cases"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(256), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    case_code: Mapped[str] = mapped_column(String(64), unique=True, index=True, nullable=False)
    summary: Mapped[str] = mapped_column(String(512), nullable=False)
    preconditions: Mapped[list[str]] = mapped_column(JSON, default=list)
    postconditions: Mapped[list[str]] = mapped_column(JSON, default=list)
    case_type: Mapped[CaseType] = mapped_column(Enum(CaseType), nullable=False)
    status: Mapped[CaseStatus] = mapped_column(Enum(CaseStatus), default=CaseStatus.draft)
    priority: Mapped[str] = mapped_column(String(8), default="P2", nullable=False)
    case_level: Mapped[str] = mapped_column(String(32), default="regression", nullable=False)
    review_status: Mapped[str] = mapped_column(String(32), default="pending", nullable=False)
    automation_status: Mapped[str] = mapped_column(String(32), default="auto", nullable=False)
    tags: Mapped[list[str]] = mapped_column(JSON, default=list)
    module_id: Mapped[int] = mapped_column(ForeignKey("modules.id"), nullable=False)
    creator_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    owner_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"))
    submitted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    reviewed_by: Mapped[int | None] = mapped_column(ForeignKey("users.id"))
    review_comment: Mapped[str | None] = mapped_column(Text)
    config: Mapped[dict] = mapped_column(JSON, default=dict)

    module: Mapped["Module"] = relationship(back_populates="cases")
    steps: Mapped[list["CaseStep"]] = relationship(
        back_populates="case",
        cascade="all, delete-orphan",
        order_by="CaseStep.step_no",
    )
    runs: Mapped[list["TestRun"]] = relationship(back_populates="case", cascade="all, delete-orphan")
    snapshots: Mapped[list["CaseSnapshot"]] = relationship(
        back_populates="case",
        cascade="all, delete-orphan",
    )

    @property
    def is_ready_for_execution(self) -> bool:
        return (
            self.status == CaseStatus.active
            and self.review_status == "approved"
            and self.automation_status in {"auto", "semi_auto"}
        )


class CaseStep(Base, TimestampMixin):
    __tablename__ = "case_steps"
    __table_args__ = (
        UniqueConstraint("case_id", "step_no", name="uq_case_steps_case_id_step_no"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    case_id: Mapped[int] = mapped_column(ForeignKey("test_cases.id", ondelete="CASCADE"), nullable=False)
    step_no: Mapped[int] = mapped_column(Integer, nullable=False)
    action: Mapped[str] = mapped_column(Text, nullable=False)
    test_data: Mapped[str | None] = mapped_column(Text)
    expected_result: Mapped[str | None] = mapped_column(Text)
    is_key_step: Mapped[bool] = mapped_column(Boolean, default=False)
    remarks: Mapped[str | None] = mapped_column(Text)

    case: Mapped["TestCase"] = relationship(back_populates="steps")


class TestRun(Base, TimestampMixin):
    __tablename__ = "test_runs"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    case_id: Mapped[int] = mapped_column(ForeignKey("test_cases.id"), nullable=False)
    triggered_by: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    status: Mapped[RunStatus] = mapped_column(Enum(RunStatus), default=RunStatus.pending)
    environment: Mapped[str | None] = mapped_column(String(64))
    duration_ms: Mapped[int | None] = mapped_column(Integer)
    error_message: Mapped[str | None] = mapped_column(Text)
    result_summary: Mapped[dict] = mapped_column(JSON, default=dict)

    case: Mapped["TestCase"] = relationship(back_populates="runs")
    steps: Mapped[list["StepResult"]] = relationship(back_populates="run", cascade="all, delete-orphan")


class StepResult(Base, TimestampMixin):
    __tablename__ = "step_results"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    run_id: Mapped[int] = mapped_column(ForeignKey("test_runs.id"), nullable=False)
    step_index: Mapped[int] = mapped_column(Integer, nullable=False)
    name: Mapped[str] = mapped_column(String(256))
    status: Mapped[RunStatus] = mapped_column(Enum(RunStatus))
    duration_ms: Mapped[int | None] = mapped_column(Integer)
    request_data: Mapped[dict | None] = mapped_column(JSON)
    response_data: Mapped[dict | None] = mapped_column(JSON)
    screenshot_url: Mapped[str | None] = mapped_column(String(512))
    error_message: Mapped[str | None] = mapped_column(Text)

    run: Mapped["TestRun"] = relationship(back_populates="steps")


class CaseSnapshot(Base, TimestampMixin):
    __tablename__ = "case_snapshots"
    __table_args__ = (
        UniqueConstraint("case_id", "version", name="uq_case_snapshots_case_id_version"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    case_id: Mapped[int] = mapped_column(ForeignKey("test_cases.id", ondelete="CASCADE"), nullable=False)
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    name: Mapped[str] = mapped_column(String(256), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    tags: Mapped[list[str]] = mapped_column(JSON, default=list)
    config: Mapped[dict] = mapped_column(JSON, default=dict)
    snapshot_data: Mapped[dict] = mapped_column(JSON, default=dict)
    updated_by: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)

    case: Mapped["TestCase"] = relationship(back_populates="snapshots")
