from datetime import datetime

from sqlalchemy import DateTime, Float, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin


class HealingFeedbackAggregate(Base, TimestampMixin):
    __tablename__ = "healing_feedback_aggregates"
    __table_args__ = (
        UniqueConstraint(
            "error_fingerprint",
            "case_type",
            name="uq_healing_feedback_aggregate_fingerprint_case_type",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    error_fingerprint: Mapped[str] = mapped_column(String(64), nullable=False)
    case_type: Mapped[str] = mapped_column(String(32), nullable=False)
    total_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    adopted_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    rejected_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    adopted_rate: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    last_aggregated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
