"""助手资产创建命令；结果与资产在同一事务提交。"""

from sqlalchemy import ForeignKey, String, Integer, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin


class HermesAction(Base, TimestampMixin):
    __tablename__ = "hermes_actions"
    __table_args__ = (UniqueConstraint("user_id", "command_id", name="uq_hermes_action_command"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    project_id: Mapped[int] = mapped_column(ForeignKey("projects.id", ondelete="CASCADE"))
    command_id: Mapped[str] = mapped_column(String(64))
    action: Mapped[str] = mapped_column(String(32))
    request_hash: Mapped[str] = mapped_column(String(64))
    resource_id: Mapped[int] = mapped_column(Integer)
    # 旧命令无法安全推断原资源身份，保留空值并在重放时要求人工核对。
    resource_identity: Mapped[str | None] = mapped_column(String(32))
