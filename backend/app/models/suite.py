import enum
from sqlalchemy import String, Text, ForeignKey, JSON, Enum, Integer
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.models.base import Base, TimestampMixin


class SuiteStatus(str, enum.Enum):
    active = "active"
    archived = "archived"


class TestSuite(Base, TimestampMixin):
    __tablename__ = "test_suites"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(256), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    project_id: Mapped[int] = mapped_column(ForeignKey("projects.id", ondelete="CASCADE"), nullable=False)
    status: Mapped[SuiteStatus] = mapped_column(Enum(SuiteStatus), default=SuiteStatus.active)
    creator_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)

    # 套件内用例列表（有序 JSON 数组）
    # 结构: [{"case_id": 1, "sort": 0}, {"case_id": 2, "sort": 1}, ...]
    case_ids: Mapped[list] = mapped_column(JSON, default=list)

    # 套件级数据驱动配置（CSV/JSON 参数化）
    # 结构: {"type": "json", "data": [{...}, {...}]} 或 {"type": "csv", "object_name": "..."}
    parameterization: Mapped[dict | None] = mapped_column(JSON, default=dict)

    # 套件执行配置
    config: Mapped[dict] = mapped_column(JSON, default=dict)

    project: Mapped["Project"] = relationship()  # noqa: F821
    runs: Mapped[list["SuiteRun"]] = relationship(back_populates="suite", cascade="all, delete-orphan")


class SuiteRunStatus(str, enum.Enum):
    pending = "pending"
    running = "running"
    passed = "passed"
    failed = "failed"
    error = "error"


class SuiteRun(Base, TimestampMixin):
    __tablename__ = "suite_runs"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    suite_id: Mapped[int] = mapped_column(ForeignKey("test_suites.id", ondelete="CASCADE"), nullable=False)
    triggered_by: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    trace_id: Mapped[str | None] = mapped_column(String(64), index=True)
    status: Mapped[SuiteRunStatus] = mapped_column(Enum(SuiteRunStatus), default=SuiteRunStatus.pending)
    environment: Mapped[str | None] = mapped_column(String(64))
    duration_ms: Mapped[int | None] = mapped_column(Integer)
    error_message: Mapped[str | None] = mapped_column(Text)

    # 结果摘要: {"total": 5, "passed": 3, "failed": 1, "error": 1}
    result_summary: Mapped[dict] = mapped_column(JSON, default=dict)

    # 每个用例的 run_id 列表
    # [{"case_id": 1, "run_id": 101, "status": "passed"}, ...]
    case_run_ids: Mapped[list] = mapped_column(JSON, default=list)

    suite: Mapped["TestSuite"] = relationship(back_populates="runs")
