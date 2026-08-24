"""Requirement records and their traceability links to test cases."""

from __future__ import annotations

from sqlalchemy import ForeignKey, Index, Integer, JSON, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin


class TestRequirement(Base, TimestampMixin):
    """A project requirement with versioned, reviewable acceptance criteria."""

    __tablename__ = "test_requirements"
    __table_args__ = (
        UniqueConstraint("project_id", "requirement_code", name="uq_test_requirements_project_code"),
        Index("ix_test_requirements_project_status", "project_id", "status"),
        Index("ix_test_requirements_project_updated", "project_id", "updated_at"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    project_id: Mapped[int] = mapped_column(ForeignKey("projects.id", ondelete="CASCADE"), nullable=False)
    requirement_code: Mapped[str | None] = mapped_column(String(64), nullable=True)
    title: Mapped[str] = mapped_column(String(256), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="draft", server_default="draft")
    priority: Mapped[str] = mapped_column(String(8), nullable=False, default="P2", server_default="P2")
    acceptance_criteria: Mapped[list[dict]] = mapped_column(JSON, nullable=False, default=list, server_default="[]")
    source: Mapped[str] = mapped_column(String(32), nullable=False, default="manual", server_default="manual")
    source_ref: Mapped[str | None] = mapped_column(String(512), nullable=True)
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1, server_default="1")
    creator_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    owner_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)

    case_links: Mapped[list["RequirementCaseLink"]] = relationship(
        back_populates="requirement",
        cascade="all, delete-orphan",
        order_by="RequirementCaseLink.created_at",
    )


class RequirementCaseLink(Base, TimestampMixin):
    """A traceability edge from one requirement to one test case."""

    __tablename__ = "requirement_case_links"
    __table_args__ = (
        UniqueConstraint(
            "requirement_id",
            "case_id",
            "relation_type",
            name="uq_requirement_case_links_relation",
        ),
        Index("ix_requirement_case_links_requirement", "requirement_id"),
        Index("ix_requirement_case_links_case", "case_id"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    requirement_id: Mapped[int] = mapped_column(
        ForeignKey("test_requirements.id", ondelete="CASCADE"),
        nullable=False,
    )
    case_id: Mapped[int] = mapped_column(ForeignKey("test_cases.id", ondelete="CASCADE"), nullable=False)
    relation_type: Mapped[str] = mapped_column(String(32), nullable=False, default="covers", server_default="covers")
    criterion_ids: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list, server_default="[]")
    note: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_by: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)

    requirement: Mapped[TestRequirement] = relationship(back_populates="case_links")
