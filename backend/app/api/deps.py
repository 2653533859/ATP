from fastapi import Depends, HTTPException, Path, Request, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from jwt import InvalidTokenError
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.security import decode_token
from app.models.project import Project
from app.models.user import User, UserRole
from app.models.user_project import ProjectRole, UserProject, role_satisfies
from app.services.audit import write_audit_log

bearer = HTTPBearer(auto_error=False)


async def get_current_user(
    request: Request,
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer),
    db: AsyncSession = Depends(get_db),
) -> User:
    # Bearer remains supported for CLI/API clients; the browser uses an HttpOnly cookie.
    token = credentials.credentials if credentials else request.cookies.get("atp_access_token")
    if not token:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated")
    try:
        payload = decode_token(token)
        if payload.get("type") != "access":
            raise InvalidTokenError("wrong token type")
        username: str = payload["sub"]
    except (InvalidTokenError, KeyError):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token")

    result = await db.execute(select(User).where(User.username == username))
    user = result.scalar_one_or_none()
    if user is None or not user.is_active:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found or inactive")
    return user


def require_roles(*roles: UserRole):
    async def checker(current_user: User = Depends(get_current_user)) -> User:
        if current_user.role not in roles:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Insufficient permissions")
        return current_user

    return checker


require_admin = require_roles(UserRole.admin)
require_engineer = require_roles(UserRole.admin, UserRole.engineer)


async def get_project_role(db: AsyncSession, user: User, project_id: int) -> ProjectRole | None:
    """全局 admin → owner；否则查 user_projects；缺则 None。"""
    if user.role == UserRole.admin:
        return ProjectRole.owner
    result = await db.execute(
        select(UserProject.role).where(UserProject.user_id == user.id, UserProject.project_id == project_id)
    )
    return result.scalar_one_or_none()


def require_project_access(min_role: ProjectRole = ProjectRole.viewer):
    """工厂依赖：校验当前用户对 path 中 `project_id` 的访问权限。

    路由必须有路径参数 `project_id`。admin 全通过；非 admin 走 UserProject 检查；
    不通过时记一条 access_denied 审计并抛 403。
    """

    async def checker(
        project_id: int = Path(..., ge=1),
        current_user: User = Depends(get_current_user),
        db: AsyncSession = Depends(get_db),
    ) -> User:
        role = await get_project_role(db, current_user, project_id)
        if role is None or not role_satisfies(role, min_role):
            await write_audit_log(
                db,
                action="access_denied",
                resource_type="project",
                resource_id=project_id,
                user_id=current_user.id,
                username=current_user.username,
                project_id=project_id,
                detail=f"min_role={min_role.value}, actual={role.value if role else 'none'}",
            )
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="No access to this project",
            )
        return current_user

    return checker


def require_project_writable_access(min_role: ProjectRole = ProjectRole.editor):
    """校验项目权限并拒绝 archived 项目的写入/执行入口。"""

    async def checker(
        project_id: int = Path(..., ge=1),
        current_user: User = Depends(get_current_user),
        db: AsyncSession = Depends(get_db),
    ) -> User:
        await assert_project_access(db, current_user, project_id, min_role)
        return current_user

    return checker


async def assert_project_access(
    db: AsyncSession, user: User, project_id: int, min_role: ProjectRole = ProjectRole.viewer
) -> None:
    """在非路径参数场景下手动断言项目访问权限。"""
    role = await get_project_role(db, user, project_id)
    if role is None or not role_satisfies(role, min_role):
        await write_audit_log(
            db,
            action="access_denied",
            resource_type="project",
            resource_id=project_id,
            user_id=user.id,
            username=user.username,
            project_id=project_id,
            detail=f"min_role={min_role.value}, actual={role.value if role else 'none'}",
        )
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="No access to this project",
        )

    # editor/owner 级断言代表写入或执行入口；归档项目保留读取、报告和导出，
    # 但不能通过任一资源 API 继续产生新配置或运行任务。兼容轻量测试桩：
    # 没有 get 方法时只验证访问角色，不改变原有单元测试的权限语义。
    if min_role != ProjectRole.viewer and hasattr(db, "get"):
        project = await db.get(Project, project_id)
        if project is not None and getattr(project, "status", "active") == "archived":
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Project is archived; restore it before writing or executing",
            )
