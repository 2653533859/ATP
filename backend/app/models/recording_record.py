"""录制历史与未保存草稿持久化模型（支持 Web 录制步骤/Trace/HAR 与 App 录制草稿恢复）。"""

from __future__ import annotations

from sqlalchemy import ForeignKey, Index, Integer, JSON, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin


class RecordingRecord(Base, TimestampMixin):
    """Persist recorded steps, draft state, and artifact object keys per session."""

    __tablename__ = "recording_records"
    __table_args__ = (
        UniqueConstraint("project_id", "kind", "session_id", name="uq_recording_records_project_kind_session_id"),
        Index("ix_recording_records_project_kind_updated", "project_id", "kind", "updated_at"),
        Index("ix_recording_records_owner_updated", "owner_id", "updated_at"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    project_id: Mapped[int] = mapped_column(ForeignKey("projects.id", ondelete="CASCADE"), nullable=False)
    owner_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    kind: Mapped[str] = mapped_column(String(16), nullable=False)
    source: Mapped[str] = mapped_column(String(32), nullable=False, default="workbench", server_default="workbench")
    session_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    target_url: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    browser: Mapped[str | None] = mapped_column(String(32), nullable=True)
    device_id: Mapped[int | None] = mapped_column(ForeignKey("devices.id", ondelete="SET NULL"), nullable=True)
    device_serial: Mapped[str | None] = mapped_column(String(128), nullable=True)
    case_id: Mapped[int | None] = mapped_column(ForeignKey("test_cases.id", ondelete="SET NULL"), nullable=True)
    status: Mapped[str] = mapped_column(String(24), nullable=False, default="draft", server_default="draft")
    steps: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    asset_ids: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    artifacts: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    summary: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
