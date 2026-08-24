"""Mappings between internal defects and issues in external trackers."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Index, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin


class DefectExternalLink(Base, TimestampMixin):
    """A project-scoped reference to an issue owned by a bug tracker."""

    __tablename__ = "defect_external_links"
    __table_args__ = (
        UniqueConstraint("defect_id", "tracker_id", "external_key", name="uq_defect_external_links_key"),
        Index("ix_defect_external_links_defect", "defect_id"),
        Index("ix_defect_external_links_tracker", "tracker_id"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    defect_id: Mapped[int] = mapped_column(ForeignKey("defects.id", ondelete="CASCADE"), nullable=False)
    tracker_id: Mapped[int] = mapped_column(ForeignKey("bug_trackers.id", ondelete="CASCADE"), nullable=False)
    external_key: Mapped[str] = mapped_column(String(128), nullable=False)
    external_url: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    external_title: Mapped[str | None] = mapped_column(String(512), nullable=True)
    external_status: Mapped[str | None] = mapped_column(String(128), nullable=True)
    sync_state: Mapped[str] = mapped_column(String(16), nullable=False, default="linked", server_default="linked")
    last_synced_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_error: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_by: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)

    defect: Mapped["Defect"] = relationship(back_populates="external_links")  # noqa: F821
    tracker: Mapped["BugTracker"] = relationship(back_populates="external_links")  # noqa: F821
