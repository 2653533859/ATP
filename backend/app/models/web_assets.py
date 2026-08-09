"""Reusable Web locator and page-object assets."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, Float, ForeignKey, Index, Integer, JSON, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin


class WebElementAsset(Base, TimestampMixin):
    __tablename__ = "web_element_assets"
    __table_args__ = (
        UniqueConstraint("project_id", "name", name="uq_web_element_assets_project_name"),
        Index("ix_web_element_assets_project_page", "project_id", "page_url"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    project_id: Mapped[int] = mapped_column(ForeignKey("projects.id", ondelete="CASCADE"), nullable=False)
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    page_url: Mapped[str | None] = mapped_column(String(512), nullable=True)
    locator: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    fallback_locators: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    owner_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    last_failed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_failure_reason: Mapped[str | None] = mapped_column(Text, nullable=True)


class WebPageObject(Base, TimestampMixin):
    __tablename__ = "web_page_objects"
    __table_args__ = (UniqueConstraint("project_id", "name", name="uq_web_page_objects_project_name"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    project_id: Mapped[int] = mapped_column(ForeignKey("projects.id", ondelete="CASCADE"), nullable=False)
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    url_pattern: Mapped[str | None] = mapped_column(String(512), nullable=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    element_refs: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    actions: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    owner_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)


class WebVisualBaseline(Base, TimestampMixin):
    """Project-scoped screenshot baseline used by Web visual assertions."""

    __tablename__ = "web_visual_baselines"
    __table_args__ = (
        UniqueConstraint("project_id", "name", name="uq_web_visual_baselines_project_name"),
        Index("ix_web_visual_baselines_project_page", "project_id", "page_url"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    project_id: Mapped[int] = mapped_column(ForeignKey("projects.id", ondelete="CASCADE"), nullable=False)
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    page_url: Mapped[str | None] = mapped_column(String(512), nullable=True)
    object_name: Mapped[str] = mapped_column(String(512), nullable=False)
    content_type: Mapped[str] = mapped_column(String(128), nullable=False, default="image/png")
    width: Mapped[int | None] = mapped_column(Integer, nullable=True)
    height: Mapped[int | None] = mapped_column(Integer, nullable=True)
    threshold: Mapped[float] = mapped_column(Float, nullable=False, default=0.01)
    pixel_threshold: Mapped[int] = mapped_column(Integer, nullable=False, default=10)
    ignore_regions: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    owner_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
