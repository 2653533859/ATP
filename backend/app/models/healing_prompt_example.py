from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, JSON, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin


class HealingPromptExample(Base, TimestampMixin):
    __tablename__ = "healing_prompt_examples"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    error_fingerprint: Mapped[str] = mapped_column(String(64), index=True, nullable=False)
    case_type: Mapped[str] = mapped_column(String(32), index=True, nullable=False)
    step_context_json: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    suggestion_text: Mapped[str] = mapped_column(Text, nullable=False)
    source_step_result_id: Mapped[int | None] = mapped_column(
        ForeignKey("step_results.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    marked_high_quality: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    marked_by: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    marked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
