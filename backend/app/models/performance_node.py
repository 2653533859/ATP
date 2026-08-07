"""Load-injector nodes used by the performance center."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import Boolean, DateTime, Integer, JSON, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin


class PerformanceNode(Base, TimestampMixin):
    __tablename__ = "performance_nodes"
    __table_args__ = (UniqueConstraint("node_id", name="uq_performance_nodes_node_id"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    node_id: Mapped[str] = mapped_column(String(128), nullable=False)
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    queue_name: Mapped[str] = mapped_column(String(128), nullable=False, default="performance")
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="offline")
    enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    labels: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    capabilities: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    max_vus: Mapped[int | None] = mapped_column(Integer, nullable=True)
    max_concurrency: Mapped[int | None] = mapped_column(Integer, nullable=True)
    egress_allowlist: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    last_heartbeat_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_error: Mapped[str | None] = mapped_column(Text, nullable=True)

    runs = relationship("PerformanceRun", back_populates="performance_node")
