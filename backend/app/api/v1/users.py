"""User administration and project-member lookup endpoints."""

import logging

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from sqlalchemy import delete, func, or_, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, require_admin
from app.api.local_scope import require_server_workspace
from app.core.database import get_db
from app.core.config import settings
from app.core.encryption import decrypt, encrypt
from app.core.security import hash_password
from app.models.system_setting import SystemSetting
from app.models.user import User, UserRole
from app.schemas.auth import InitialPasswordUpdate, UserAdminCreate, UserAdminUpdate, UserLookupOut, UserOut
from app.services.audit import write_audit_log

router = APIRouter(prefix="/users", tags=["用户管理"])
logger = logging.getLogger(__name__)
_INITIAL_PASSWORD_KEY = "user_initial_password"


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


async def _collect_blocking_user_assets(db: AsyncSession, user_id: int) -> list[str]:
    """统计会阻塞物理删除的核心业务外键引用，返回可读摘要列表。"""
    from app.models import load_all_models
    from app.models.apk import Apk
    from app.models.case import CaseSnapshot, TestCase, TestRun
    from app.models.dataset import TestDataset
    from app.models.ios import IosApp
    from app.models.mock import MockRule
    from app.models.mock_snapshot import MockRuleSnapshot
    from app.models.plan import TestPlan
    from app.models.project import Project
    from app.models.requirement import TestRequirement
    from app.models.suite import SuiteRun, TestSuite

    load_all_models()
    asset_groups: list[tuple[str, str, list[tuple[object, object]]]] = [
        ("项目", "个", [(Project.id, Project.owner_id)]),
        ("测试用例", "条", [(TestCase.id, TestCase.creator_id)]),
        ("用例快照", "条", [(CaseSnapshot.id, CaseSnapshot.updated_by)]),
        ("执行记录", "条", [(TestRun.id, TestRun.triggered_by)]),
        ("测试套件与运行", "条", [(TestSuite.id, TestSuite.creator_id), (SuiteRun.id, SuiteRun.triggered_by)]),
        ("测试计划", "个", [(TestPlan.id, TestPlan.creator_id)]),
        ("测试数据集", "个", [(TestDataset.id, TestDataset.creator_id)]),
        (
            "Mock 规则与快照",
            "条",
            [(MockRule.id, MockRule.creator_id), (MockRuleSnapshot.id, MockRuleSnapshot.changed_by)],
        ),
        ("需求文档", "条", [(TestRequirement.id, TestRequirement.creator_id)]),
        ("安装包资产", "个", [(Apk.id, Apk.uploaded_by), (IosApp.id, IosApp.uploaded_by)]),
    ]
    blocking: list[str] = []
    for label, unit, pairs in asset_groups:
        total = 0
        for id_col, fk_col in pairs:
            total += int((await db.scalar(select(func.count(id_col)).where(fk_col == user_id))) or 0)
        if total > 0:
            blocking.append(f"{label} {total} {unit}")
    return blocking


async def _detach_deletable_user_references(db: AsyncSession, user_id: int) -> None:
    """删除用户前清理个人偏好记录并将未配置级联的可空外键置空。"""
    from app.models import load_all_models
    from app.models.case import TestCase
    from app.models.dataset import TestDatasetVersion
    from app.models.healing_prompt_example import HealingPromptExample
    from app.models.plan import PlanRun
    from app.models.user_setting import UserSetting

    load_all_models()
    await db.execute(delete(UserSetting).where(UserSetting.user_id == user_id))
    await db.execute(update(TestCase).where(TestCase.owner_id == user_id).values(owner_id=None))
    await db.execute(update(TestCase).where(TestCase.reviewed_by == user_id).values(reviewed_by=None))
    await db.execute(update(TestDatasetVersion).where(TestDatasetVersion.created_by == user_id).values(created_by=None))
    await db.execute(
        update(HealingPromptExample).where(HealingPromptExample.marked_by == user_id).values(marked_by=None)
    )
    await db.execute(update(PlanRun).where(PlanRun.triggered_by == user_id).values(triggered_by=None))


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


@router.get("/initial-password")
async def get_initial_password(
    response: Response, db: AsyncSession = Depends(get_db), _: User = Depends(require_admin)
):
    """仅管理员可读取新增用户默认密码。"""
    require_server_workspace("读取新增用户默认密码")
    response.headers["Cache-Control"] = "no-store"
    setting = await db.get(SystemSetting, _INITIAL_PASSWORD_KEY)
    if setting is None:
        return {"password": settings.DEFAULT_USER_INITIAL_PASSWORD}
    try:
        password = decrypt(setting.value_encrypted)
    except Exception:
        # 密钥轮换或跨机还原会让历史密文失效，此时回退内置默认值而不是 500。
        logger.warning("Failed to decrypt %s; falling back to the built-in default", _INITIAL_PASSWORD_KEY)
        password = settings.DEFAULT_USER_INITIAL_PASSWORD
    return {"password": password}


@router.put("/initial-password")
async def update_initial_password(
    body: InitialPasswordUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    """加密保存全局初始密码；现有用户密码不受影响。"""
    require_server_workspace("修改用户默认初始密码")
    setting = await db.get(SystemSetting, _INITIAL_PASSWORD_KEY)
    if setting is None:
        setting = SystemSetting(key=_INITIAL_PASSWORD_KEY, value_encrypted=encrypt(body.password))
        db.add(setting)
    else:
        setting.value_encrypted = encrypt(body.password)
    try:
        await db.flush()
        await write_audit_log(
            db,
            action="update_initial_password",
            resource_type="system_setting",
            user_id=current_user.id,
            username=current_user.username,
            detail="更新新增用户默认初始密码",
        )
        await db.commit()
    except IntegrityError as exc:
        await db.rollback()
        raise HTTPException(status_code=409, detail="设置已被其他管理员修改，请重试") from exc
    return {"success": True}


@router.post("", response_model=UserOut, status_code=status.HTTP_201_CREATED)
async def create_user(
    body: UserAdminCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    require_server_workspace("添加用户")
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
    require_server_workspace("管理其他用户")
    user = await db.get(User, user_id)
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="用户不存在")

    username = body.username.strip() if body.username is not None else user.username
    email = str(body.email) if body.email is not None else user.email
    new_role = _role(body.role) if body.role is not None else user.role
    new_is_active = body.is_active if body.is_active is not None else user.is_active
    if user.id == current_user.id:
        if not new_is_active:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="不能停用当前登录账号")
        if new_role != UserRole.admin:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="不能降级当前登录管理员角色")
        if username != user.username:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="请前往「账号设置」修改当前登录账号的用户名",
            )
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


@router.delete("/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_user(
    user_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    require_server_workspace("删除用户")
    if user_id == current_user.id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="不能删除当前登录账号")
    user = await db.get(User, user_id)
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="用户不存在")
    await _assert_active_admin_remains(db, user, user.role, False)
    blocking_assets = await _collect_blocking_user_assets(db, user_id)
    if blocking_assets:
        summary = "、".join(blocking_assets)
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"该用户仍关联历史业务资产（{summary}），无法直接删除，请通过禁用账号保留审计完整",
        )
    username = user.username
    try:
        await _detach_deletable_user_references(db, user_id)
        await db.delete(user)
        await db.flush()
        await write_audit_log(
            db,
            action="delete_user",
            resource_type="user",
            resource_id=user_id,
            user_id=current_user.id,
            username=current_user.username,
            detail=f"删除用户 {username}",
        )
        await db.commit()
    except IntegrityError as exc:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="该用户已关联历史用例或执行记录，请通过禁用账号 (is_active=false) 保留审计完整",
        ) from exc
