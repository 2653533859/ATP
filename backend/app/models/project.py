from typing import TYPE_CHECKING

from sqlalchemy import String, Text, ForeignKey, Integer
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.models.base import Base, TimestampMixin

if TYPE_CHECKING:
    from app.models.bug_tracker import BugTracker
    from app.models.case import TestCase
    from app.models.dashboard_alert import DashboardAlertRule
    from app.models.mobile_special import MobileSpecialTask
    from app.models.notification import NotificationConfig


class Project(Base, TimestampMixin):
    __tablename__ = "projects"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    project_code: Mapped[str | None] = mapped_column(String(32), unique=True)
    description: Mapped[str | None] = mapped_column(Text)
    owner_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    ai_llm_config_id: Mapped[int | None] = mapped_column(ForeignKey("ai_llm_configs.id"))
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="active", server_default="active")
    # P1.4：项目级保留天数覆盖；None 表示沿用全局 RUN_RETENTION_DAYS
    run_retention_days_override: Mapped[int | None] = mapped_column(Integer)

    modules: Mapped[list["Module"]] = relationship(back_populates="project", cascade="all, delete-orphan")
    notifications: Mapped[list["NotificationConfig"]] = relationship(
        back_populates="project",
        cascade="all, delete-orphan",
    )
    bug_trackers: Mapped[list["BugTracker"]] = relationship(
        back_populates="project",
        cascade="all, delete-orphan",
    )
    mobile_special_tasks: Mapped[list["MobileSpecialTask"]] = relationship(
        back_populates="project",
        cascade="all, delete-orphan",
    )
    dashboard_alert_rules: Mapped[list["DashboardAlertRule"]] = relationship(
        back_populates="project",
        cascade="all, delete-orphan",
    )


class Module(Base, TimestampMixin):
    __tablename__ = "modules"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    module_code: Mapped[str | None] = mapped_column(String(32))
    project_id: Mapped[int] = mapped_column(ForeignKey("projects.id"), nullable=False)
    parent_id: Mapped[int | None] = mapped_column(ForeignKey("modules.id"))
    sort_order: Mapped[int] = mapped_column(Integer, default=0)

    project: Mapped["Project"] = relationship(back_populates="modules")
    children: Mapped[list["Module"]] = relationship(back_populates="parent")
    parent: Mapped["Module | None"] = relationship(back_populates="children", remote_side="Module.id")
    cases: Mapped[list["TestCase"]] = relationship(back_populates="module", cascade="all, delete-orphan")
