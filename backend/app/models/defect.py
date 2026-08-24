"""Internal project defects and their execution/evidence links."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Index, Integer, JSON, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin


class Defect(Base, TimestampMixin):
    """A project-owned defect independent from external issue trackers."""

    __tablename__ = "defects"
    __table_args__ = (
        Index("ix_defects_project_status", "project_id", "status"),
        Index("ix_defects_project_fingerprint", "project_id", "fingerprint"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    project_id: Mapped[int] = mapped_column(ForeignKey("projects.id", ondelete="CASCADE"), nullable=False)
    case_id: Mapped[int | None] = mapped_column(ForeignKey("test_cases.id", ondelete="SET NULL"), nullable=True)
    title: Mapped[str] = mapped_column(String(256), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="open", server_default="open")
    priority: Mapped[str] = mapped_column(String(8), nullable=False, default="P2", server_default="P2")
    severity: Mapped[str] = mapped_column(String(32), nullable=False, default="major", server_default="major")
    fingerprint: Mapped[str | None] = mapped_column(String(128), nullable=True)
    resolution: Mapped[str | None] = mapped_column(String(64), nullable=True)
    labels: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list, server_default="[]")
    occurrence_count: Mapped[int] = mapped_column(Integer, nullable=False, default=1, server_default="1")
    last_seen_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    creator_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    assignee_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)

    run_links: Mapped[list["DefectRunLink"]] = relationship(
        back_populates="defect",
        cascade="all, delete-orphan",
        order_by="DefectRunLink.created_at",
    )


class DefectRunLink(Base, TimestampMixin):
    """Polymorphic link to a run type while retaining sanitized evidence."""

    __tablename__ = "defect_run_links"
    __table_args__ = (
        UniqueConstraint("defect_id", "run_type", "run_id", name="uq_defect_run_links_defect_run"),
        Index("ix_defect_run_links_run", "run_type", "run_id"),
        Index("ix_defect_run_links_case", "case_id"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    defect_id: Mapped[int] = mapped_column(ForeignKey("defects.id", ondelete="CASCADE"), nullable=False)
    run_type: Mapped[str] = mapped_column(String(32), nullable=False)
    run_id: Mapped[int] = mapped_column(Integer, nullable=False)
    case_id: Mapped[int | None] = mapped_column(ForeignKey("test_cases.id", ondelete="SET NULL"), nullable=True)
    evidence: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict, server_default="{}")
    linked_by: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)

    defect: Mapped[Defect] = relationship(back_populates="run_links")
