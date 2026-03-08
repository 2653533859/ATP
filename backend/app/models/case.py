import enum
from sqlalchemy import String, Text, ForeignKey, JSON, Enum, Integer, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.models.base import Base, TimestampMixin
from app.models.project import Module  # noqa: F401 - 确保关系加载


class CaseType(str, enum.Enum):
    api = "api"
    web = "web"
    android = "android"
    graphql = "graphql"
    websocket = "websocket"
    grpc = "grpc"


class CaseStatus(str, enum.Enum):
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
    case_type: Mapped[CaseType] = mapped_column(Enum(CaseType), nullable=False)
    status: Mapped[CaseStatus] = mapped_column(Enum(CaseStatus), default=CaseStatus.active)
    tags: Mapped[list] = mapped_column(JSON, default=list)
    module_id: Mapped[int] = mapped_column(ForeignKey("modules.id"), nullable=False)
    creator_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)

    # 用例配置存储为 JSON（不同类型结构不同）
    config: Mapped[dict] = mapped_column(JSON, default=dict)

    module: Mapped["Module"] = relationship(back_populates="cases")
    runs: Mapped[list["TestRun"]] = relationship(back_populates="case", cascade="all, delete-orphan")
    snapshots: Mapped[list["CaseSnapshot"]] = relationship(back_populates="case", cascade="all, delete-orphan")


class TestRun(Base, TimestampMixin):
    __tablename__ = "test_runs"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    case_id: Mapped[int] = mapped_column(ForeignKey("test_cases.id"), nullable=False)
    triggered_by: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    status: Mapped[RunStatus] = mapped_column(Enum(RunStatus), default=RunStatus.pending)
    environment: Mapped[str | None] = mapped_column(String(64))
    duration_ms: Mapped[int | None] = mapped_column(Integer)
    error_message: Mapped[str | None] = mapped_column(Text)

    # 执行结果摘要
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
    tags: Mapped[list] = mapped_column(JSON, default=list)
    config: Mapped[dict] = mapped_column(JSON, default=dict)
    updated_by: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)

    case: Mapped["TestCase"] = relationship(back_populates="snapshots")
