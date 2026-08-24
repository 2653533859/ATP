"""Encrypted, auditable snapshots of configuration resources."""

from __future__ import annotations

from sqlalchemy import ForeignKey, Index, Integer, JSON, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin


class ConfigurationRevision(Base, TimestampMixin):
    """A point-in-time snapshot for one configuration resource.

    ``resource_id`` is intentionally polymorphic: configuration domains use
    different tables, and a snapshot must remain readable after the original
    resource is deleted.  The raw payload is encrypted at application level;
    ``redacted_payload`` never contains secret values and is safe to return.
    """

    __tablename__ = "configuration_revisions"
    __table_args__ = (
        Index(
            "ix_configuration_revisions_domain_resource_created",
            "domain",
            "resource_id",
            "created_at",
        ),
        Index(
            "ix_configuration_revisions_project_created",
            "project_id",
            "created_at",
        ),
        Index("ix_configuration_revisions_fingerprint", "fingerprint"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    domain: Mapped[str] = mapped_column(String(32), nullable=False)
    resource_id: Mapped[int] = mapped_column(Integer, nullable=False)
    project_id: Mapped[int | None] = mapped_column(ForeignKey("projects.id", ondelete="CASCADE"), nullable=True)
    resource_name: Mapped[str] = mapped_column(String(256), nullable=False)
    payload_encrypted: Mapped[str] = mapped_column(Text, nullable=False)
    redacted_payload: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    fingerprint: Mapped[str] = mapped_column(String(64), nullable=False)
    reason: Mapped[str | None] = mapped_column(String(512), nullable=True)
    created_by: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
