"""Database model for Cloud-persisted test run summaries (D3)."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, Integer, JSON, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin


class CloudRunSummaryModel(Base, TimestampMixin):
    """Aggregated lightweight test run summary received from client desktop nodes."""

    __tablename__ = "cloud_run_summaries"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    client_id: Mapped[str] = mapped_column(String(64), index=True, nullable=False)
    machine_name: Mapped[str] = mapped_column(String(64), nullable=False)
    unique_key: Mapped[str] = mapped_column(String(128), unique=True, index=True, nullable=False)
    run_type: Mapped[str] = mapped_column(String(32), index=True, nullable=False)
    run_id: Mapped[int] = mapped_column(Integer, nullable=False)
    project_name: Mapped[str] = mapped_column(String(128), nullable=False)
    project_code: Mapped[str] = mapped_column(String(64), index=True, nullable=False)
    title: Mapped[str] = mapped_column(String(256), nullable=False)
    status: Mapped[str] = mapped_column(String(32), index=True, nullable=False)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    duration_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    triggered_by: Mapped[str] = mapped_column(String(64), nullable=False, default="admin")
    environment: Mapped[str | None] = mapped_column(String(64), nullable=True)
    metrics: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    error_summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    steps_summary: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    reported_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
