"""P3.C 多租户隔离：用户与项目的 N:N 成员表 + 项目内角色。

项目内角色与全局 UserRole 解耦：
- owner: 项目管理（成员/通知/集成/删除）
- editor: 创建/编辑/删除资源、触发执行
- viewer: 只读
"""
import enum
from datetime import datetime

from sqlalchemy import DateTime, Enum, ForeignKey, Integer, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class ProjectRole(str, enum.Enum):
    owner = "owner"
    editor = "editor"
    viewer = "viewer"


_ROLE_RANK = {ProjectRole.viewer: 1, ProjectRole.editor: 2, ProjectRole.owner: 3}


def role_rank(role: ProjectRole) -> int:
    return _ROLE_RANK[role]


def role_satisfies(actual: ProjectRole, required: ProjectRole) -> bool:
    return role_rank(actual) >= role_rank(required)


class UserProject(Base):
    __tablename__ = "user_projects"
    __table_args__ = (
        UniqueConstraint("user_id", "project_id", name="uq_user_projects_user_project"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    project_id: Mapped[int] = mapped_column(ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, index=True)
    role: Mapped[ProjectRole] = mapped_column(Enum(ProjectRole), nullable=False, default=ProjectRole.viewer)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
