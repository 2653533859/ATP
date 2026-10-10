"""Persist child ownership before starting or dispatching a child execution."""

from sqlalchemy import Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin


class GroupRunChild(Base, TimestampMixin):
    __tablename__ = "group_run_children"
    __table_args__ = (
        UniqueConstraint(
            "parent_kind", "parent_identity", "child_id", "child_identity", name="uq_group_run_children_identity"
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    parent_kind: Mapped[str] = mapped_column(String(16), nullable=False)
    parent_run_id: Mapped[int] = mapped_column(Integer, nullable=False)
    parent_identity: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    child_kind: Mapped[str] = mapped_column(String(16), nullable=False)
    child_id: Mapped[int] = mapped_column(Integer, nullable=False)
    child_identity: Mapped[str] = mapped_column(String(128), nullable=False)
