from sqlalchemy import Boolean, Float, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin


class StoragePolicy(Base, TimestampMixin):
    __tablename__ = "storage_policies"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    prefix: Mapped[str] = mapped_column(String(128), unique=True, nullable=False)
    retention_days: Mapped[int] = mapped_column(Integer, nullable=False, default=30)
    max_size_gb: Mapped[float | None] = mapped_column(Float, nullable=True)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
