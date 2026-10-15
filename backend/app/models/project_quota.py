"""Project Quota and Concurrency Resource Model (Q4.1)."""

from __future__ import annotations

from sqlalchemy import Boolean, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin


class ProjectQuota(Base, TimestampMixin):
    __tablename__ = "project_quotas"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    project_id: Mapped[int] = mapped_column(
        ForeignKey("projects.id", ondelete="CASCADE"),
        unique=True,
        index=True,
        nullable=False,
    )
    max_concurrent_runs: Mapped[int] = mapped_column(Integer, nullable=False, default=5, server_default="5")
    daily_duration_limit_seconds: Mapped[int] = mapped_column(
        Integer, nullable=False, default=28800, server_default="28800"
    )
    max_single_run_timeout_seconds: Mapped[int] = mapped_column(
        Integer, nullable=False, default=3600, server_default="3600"
    )
    over_quota_policy: Mapped[str] = mapped_column(
        String(16), nullable=False, default="reject", server_default="reject"
    )
    is_enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, server_default="true")
    description: Mapped[str | None] = mapped_column(Text)
