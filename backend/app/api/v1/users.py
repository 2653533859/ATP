"""User administration and project-member lookup endpoints."""

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, require_admin
from app.core.database import get_db
from app.core.security import hash_password
from app.models.user import User, UserRole
from app.schemas.auth import UserAdminCreate, UserAdminUpdate, UserLookupOut, UserOut
from app.services.audit import write_audit_log

router = APIRouter(prefix="/users", tags=["用户管理"])


def _role(value: str) -> UserRole:
    try:
        return UserRole(value)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail="无效的用户角色") from exc


async def _assert_unique(db: AsyncSession, username: str, email: str, user_id: int | None = None) -> None:
    conditions = [User.username == username, User.email == email]
    query = select(User).where(or_(*conditions))
    if user_id is not None:
        query = query.where(User.id != user_id)
    if (await db.execute(query)).scalar_one_or_none() is not None:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="用户名或邮箱已被使用")


async def _assert_active_admin_remains(
    db: AsyncSession,
    target: User,
    new_role: UserRole,
    new_is_active: bool,
) -> None:
    if target.role != UserRole.admin or (new_role == UserRole.admin and new_is_active):
        return
    count = await db.scalar(
        select(func.count(User.id)).where(
            User.id != target.id,
            User.role == UserRole.admin,
            User.is_active.is_(True),
        )
    )
    if not count:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="不能停用或降级最后一个管理员")


@router.get("/lookup", response_model=list[UserLookupOut])
async def lookup_users(
    username: str = Query(..., min_length=1, max_length=64),
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_user),
):
    """为项目成员选择提供最小化的活跃用户搜索结果。"""
    keyword = username.strip()
    if not keyword:
        return []
    result = await db.execute(
        select(User)
        .where(User.is_active.is_(True), User.username.ilike(f"%{keyword}%"))
        .order_by(User.username.asc())
        .limit(20)
    )
    return result.scalars().all()


@router.get("", response_model=list[UserOut])
async def list_users(
    username: str | None = Query(None, max_length=64),
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_admin),
):
    query = select(User).order_by(User.id.asc())
    if username and username.strip():
        query = query.where(User.username.ilike(f"%{username.strip()}%"))
    result = await db.execute(query)
    return result.scalars().all()


@router.post("", response_model=UserOut, status_code=status.HTTP_201_CREATED)
async def create_user(
    body: UserAdminCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    username = body.username.strip()
    email = str(body.email)
    await _assert_unique(db, username, email)
    user = User(
        username=username,
        email=email,
        hashed_password=hash_password(body.password),
        role=_role(body.role),
        is_active=body.is_active,
    )
    db.add(user)
    try:
        await db.flush()
        await write_audit_log(
            db,
            action="create_user",
            resource_type="user",
            resource_id=user.id,
            user_id=current_user.id,
            username=current_user.username,
            detail=f"创建用户 {user.username}",
        )
        await db.commit()
    except IntegrityError as exc:
        await db.rollback()
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="用户名或邮箱已被使用") from exc
    await db.refresh(user)
    return user


@router.patch("/{user_id}", response_model=UserOut)
async def update_user(
    user_id: int,
    body: UserAdminUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    user = await db.get(User, user_id)
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="用户不存在")

    username = body.username.strip() if body.username is not None else user.username
    email = str(body.email) if body.email is not None else user.email
    new_role = _role(body.role) if body.role is not None else user.role
    new_is_active = body.is_active if body.is_active is not None else user.is_active
    await _assert_unique(db, username, email, user_id=user.id)
    await _assert_active_admin_remains(db, user, new_role, new_is_active)

    user.username = username
    user.email = email
    user.role = new_role
    user.is_active = new_is_active
    if body.password is not None:
        user.hashed_password = hash_password(body.password)
    try:
        await write_audit_log(
            db,
            action="update_user",
            resource_type="user",
            resource_id=user.id,
            user_id=current_user.id,
            username=current_user.username,
            detail=f"更新用户 {user.username}",
        )
        await db.commit()
    except IntegrityError as exc:
        await db.rollback()
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="用户名或邮箱已被使用") from exc
    await db.refresh(user)
    return user
