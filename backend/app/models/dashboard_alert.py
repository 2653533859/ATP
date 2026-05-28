import enum
from datetime import datetime

from sqlalchemy import Boolean, DateTime, Enum, Float, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin


class DashboardAlertMetric(str, enum.Enum):
    pass_rate = "pass_rate"
    avg_duration_ms = "avg_duration_ms"
    failure_count = "failure_count"
    error_count = "error_count"
    total_runs = "total_runs"


class DashboardAlertOperator(str, enum.Enum):
    gt = "gt"
    gte = "gte"
    lt = "lt"
    lte = "lte"
    eq = "eq"


class DashboardAlertRule(Base, TimestampMixin):
    __tablename__ = "dashboard_alert_rules"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    project_id: Mapped[int] = mapped_column(ForeignKey("projects.id", ondelete="CASCADE"), nullable=False)
    metric: Mapped[DashboardAlertMetric] = mapped_column(Enum(DashboardAlertMetric), nullable=False)
    op: Mapped[DashboardAlertOperator] = mapped_column(Enum(DashboardAlertOperator), nullable=False)
    threshold: Mapped[float] = mapped_column(Float, nullable=False)
    window_minutes: Mapped[int] = mapped_column(Integer, default=60, nullable=False)
    suppress_minutes: Mapped[int] = mapped_column(Integer, default=60, nullable=False)
    notification_config_id: Mapped[int | None] = mapped_column(
        ForeignKey("notification_configs.id", ondelete="SET NULL")
    )
    enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    project: Mapped["Project"] = relationship(back_populates="dashboard_alert_rules")  # noqa: F821
    notification_config: Mapped["NotificationConfig | None"] = relationship()  # noqa: F821
    events: Mapped[list["DashboardAlertEvent"]] = relationship(
        back_populates="rule",
        cascade="all, delete-orphan",
    )


class DashboardAlertEvent(Base, TimestampMixin):
    __tablename__ = "dashboard_alert_events"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    rule_id: Mapped[int] = mapped_column(
        ForeignKey("dashboard_alert_rules.id", ondelete="CASCADE"),
        nullable=False,
    )
    triggered_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    actual_value: Mapped[float] = mapped_column(Float, nullable=False)
    snoozed_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    rule: Mapped[DashboardAlertRule] = relationship(back_populates="events")
