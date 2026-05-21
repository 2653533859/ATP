"""Mock 规则版本快照：每次更新规则前写入旧状态，支持回滚。"""
from sqlalchemy import ForeignKey, Integer, JSON, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin


class MockRuleSnapshot(Base, TimestampMixin):
    __tablename__ = "mock_rule_snapshots"
    __table_args__ = (
        UniqueConstraint("rule_id", "version", name="uq_mock_rule_snapshots_rule_id_version"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    rule_id: Mapped[int] = mapped_column(
        ForeignKey("mock_rules.id", ondelete="CASCADE"), nullable=False, index=True
    )
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    snapshot_data: Mapped[dict] = mapped_column(JSON, default=dict)
    note: Mapped[str | None] = mapped_column(Text)
    changed_by: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)

    rule: Mapped["MockRule"] = relationship()  # noqa: F821
