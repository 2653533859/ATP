"""远程桌面节点授权：按用户或项目授予只读/读写（D5 多用户授权）。

一条授权记录绑定 (node_client_id, 用户或项目)。user_id 与 project_id 互斥；
撤销采用 revoked_at 软删除，保留完整审计轨迹。生效规则见
``app/api/v1/remote_nodes.py``：admin 全局直通；直接用户授权与"项目授权 ×
项目成员"取并集后取最高权限；全局 viewer 角色与项目 viewer 成员被钳制为只读。
"""

from datetime import datetime

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Index, Integer, String, text
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin


class RemoteNodeGrant(Base, TimestampMixin):
    __tablename__ = "remote_node_grants"
    __table_args__ = (
        CheckConstraint("(user_id IS NULL) <> (project_id IS NULL)", name="ck_remote_node_grants_subject_exclusive"),
        Index(
            "uq_remote_node_grants_active_user",
            "node_client_id",
            "user_id",
            unique=True,
            sqlite_where=text("revoked_at IS NULL"),
            postgresql_where=text("revoked_at IS NULL"),
        ),
        Index(
            "uq_remote_node_grants_active_project",
            "node_client_id",
            "project_id",
            unique=True,
            sqlite_where=text("revoked_at IS NULL"),
            postgresql_where=text("revoked_at IS NULL"),
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    node_client_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=True)
    project_id: Mapped[int | None] = mapped_column(ForeignKey("projects.id", ondelete="CASCADE"), nullable=True)
    access_level: Mapped[str] = mapped_column(String(16), nullable=False)
    created_by_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    revoked_by_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
