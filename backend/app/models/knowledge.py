"""Knowledge hub entries shared by project-scoped testing workflows."""

from __future__ import annotations

from sqlalchemy import ForeignKey, Index, Integer, JSON, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin


class KnowledgeEntry(Base, TimestampMixin):
    """A reviewable knowledge article owned by a project or the platform."""

    __tablename__ = "knowledge_entries"
    __table_args__ = (
        Index("ix_knowledge_entries_project_status", "project_id", "status"),
        Index("ix_knowledge_entries_project_source", "project_id", "source_type"),
        Index("ix_knowledge_entries_project_updated", "project_id", "updated_at"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    # NULL means a platform-wide article. Project deletion cascades project articles
    # instead of accidentally turning them into globally visible content.
    project_id: Mapped[int | None] = mapped_column(
        ForeignKey("projects.id", ondelete="CASCADE"),
        nullable=True,
    )
    source_type: Mapped[str] = mapped_column(
        String(32), nullable=False, default="experience", server_default="experience"
    )
    title: Mapped[str] = mapped_column(String(256), nullable=False)
    summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    source_ref: Mapped[str | None] = mapped_column(String(512), nullable=True)
    tags: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list, server_default="[]")
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="draft", server_default="draft")
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1, server_default="1")
    author_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
