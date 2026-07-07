"""P3.B 测试数据集模型。

CSV / JSON 数据集，行数据直存 JSON 字段（rows）；MVP 限制 ≤500 行 ≤256KB。
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import ForeignKey, Integer, JSON, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin


class TestDataset(Base, TimestampMixin):
    __tablename__ = "test_datasets"
    __table_args__ = (UniqueConstraint("project_id", "name", name="uq_test_datasets_project_name"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    project_id: Mapped[int] = mapped_column(ForeignKey("projects.id", ondelete="CASCADE"), nullable=False)
    format: Mapped[str] = mapped_column(String(16), nullable=False, default="json")
    rows: Mapped[list[dict]] = mapped_column(JSON, nullable=False, default=list)
    schema_fields: Mapped[list[dict]] = mapped_column(JSON, nullable=False, default=list)
    validation_policy: Mapped[str] = mapped_column(String(16), nullable=False, default="soft")
    creator_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)


class TestDatasetVersion(Base, TimestampMixin):
    __tablename__ = "test_dataset_versions"
    __table_args__ = (UniqueConstraint("dataset_id", "version", name="uq_test_dataset_versions_dataset_version"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    dataset_id: Mapped[int] = mapped_column(
        ForeignKey("test_datasets.id", ondelete="CASCADE"), nullable=False, index=True
    )
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    format: Mapped[str] = mapped_column(String(16), nullable=False, default="json")
    rows: Mapped[list[dict]] = mapped_column(JSON, nullable=False, default=list)
    schema_fields: Mapped[list[dict]] = mapped_column(JSON, nullable=False, default=list)
    validation_policy: Mapped[str] = mapped_column(String(16), nullable=False, default="soft")
    change_type: Mapped[str] = mapped_column(String(32), nullable=False, default="manual")
    created_by: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
