"""Global Variables API endpoints."""

from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.encryption import encrypt, decrypt
from app.models.global_variable import GlobalVariable, ScopeType
from app.schemas.global_variable import (
    GlobalVariableCreate,
    GlobalVariableUpdate,
    GlobalVariableRead,
)
from app.api.deps import assert_project_access, assert_project_role, get_current_user
from app.models.user import User, UserRole
from app.models.user_project import ProjectRole
from app.services.project_scope import visible_project_ids

router = APIRouter(prefix="/global-variables", tags=["全局变量库"])


def _mask_value(value: str, is_secret: bool) -> str:
    """Mask secret values for API responses."""
    if is_secret:
        if len(value) <= 4:
            return "*" * len(value)
        return value[:2] + "*" * (len(value) - 4) + value[-2:]
    return value


def _serialize_variable(var: GlobalVariable, reveal_secret: bool = False) -> GlobalVariableRead:
    try:
        plain_value = decrypt(var.value_encrypted)
    except Exception:
        plain_value = var.value_encrypted

    value = plain_value if (reveal_secret or not var.is_secret) else _mask_value(plain_value, True)
    return GlobalVariableRead(
        id=var.id,
        scope_type=var.scope_type,
        project_id=var.project_id,
        key=var.key,
        value=value,
        is_secret=var.is_secret,
        description=var.description,
        created_at=var.created_at,
        updated_at=var.updated_at,
    )


@router.get("", response_model=list[GlobalVariableRead])
async def list_variables(
    project_id: int | None = None,
    scope_type: ScopeType | None = None,
    db: AsyncSession = Depends(get_db),
    user=Depends(get_current_user),
):
    """List global variables. Secrets are masked in the response."""
    if project_id is not None:
        await assert_project_access(db, user, project_id, ProjectRole.viewer)
    q = select(GlobalVariable).order_by(GlobalVariable.key.asc())
    if scope_type is not None:
        q = q.where(GlobalVariable.scope_type == scope_type)
    if project_id is not None:
        q = q.where(GlobalVariable.project_id == project_id)
    elif user.role != UserRole.admin:
        q = q.where(
            or_(
                GlobalVariable.scope_type == ScopeType.global_scope,
                GlobalVariable.project_id.in_(visible_project_ids(user)),
            )
        )
    result = await db.execute(q)
    variables = result.scalars().all()
    return [_serialize_variable(var) for var in variables]


@router.post("", response_model=GlobalVariableRead, status_code=status.HTTP_201_CREATED)
async def create_variable(
    body: GlobalVariableCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Create a new global variable. Encrypts the value before storing."""
    # 全局作用域要求 admin；项目作用域要求项目内 editor
    if body.scope_type == ScopeType.project:
        if body.project_id is None:
            raise HTTPException(status_code=400, detail="项目作用域变量必须指定 project_id")
        await assert_project_access(db, current_user, body.project_id, ProjectRole.editor)
    elif body.scope_type == ScopeType.global_scope:
        if body.project_id is not None:
            raise HTTPException(status_code=400, detail="全局作用域变量不能指定 project_id")
        if current_user.role != UserRole.admin:
            raise HTTPException(status_code=403, detail="只有管理员可以创建全局作用域变量")
    # 检查 key 唯一性
    q = select(GlobalVariable).where(
        GlobalVariable.key == body.key,
        GlobalVariable.scope_type == body.scope_type,
    )
    if body.project_id is not None:
        q = q.where(GlobalVariable.project_id == body.project_id)
    existing = await db.execute(q)
    if existing.scalars().first():
        raise HTTPException(status_code=400, detail=f"Variable with key '{body.key}' already exists")

    encrypted_value = encrypt(body.value_encrypted)

    var = GlobalVariable(
        **body.model_dump(exclude={"value_encrypted", "created_by"}),
        value_encrypted=encrypted_value,
        created_by=current_user.id,
    )
    db.add(var)
    await db.commit()
    await db.refresh(var)
    return _serialize_variable(var)


@router.get("/{var_id}", response_model=GlobalVariableRead)
async def get_variable(
    var_id: int,
    reveal_secret: bool = Query(default=False),
    db: AsyncSession = Depends(get_db),
    user=Depends(get_current_user),
):
    """Get a specific variable."""
    var = await db.get(GlobalVariable, var_id)
    if not var:
        raise HTTPException(status_code=404, detail="Variable not found")
    if var.project_id is not None:
        await assert_project_access(db, user, var.project_id, ProjectRole.viewer)
    if reveal_secret and var.is_secret:
        if var.project_id is None:
            if user.role != UserRole.admin:
                raise HTTPException(status_code=403, detail="只有管理员可以查看全局密钥明文")
        else:
            await assert_project_role(db, user, var.project_id, ProjectRole.editor)
    return _serialize_variable(var, reveal_secret=reveal_secret)


@router.patch("/{var_id}", response_model=GlobalVariableRead)
async def update_variable(
    var_id: int,
    body: GlobalVariableUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Update a variable. If value is changed, re-encrypts it."""
    var = await db.get(GlobalVariable, var_id)
    if not var:
        raise HTTPException(status_code=404, detail="Variable not found")
    if var.project_id is not None:
        await assert_project_access(db, current_user, var.project_id, ProjectRole.editor)
    elif current_user.role != UserRole.admin:
        raise HTTPException(status_code=403, detail="只有管理员可以修改全局作用域变量")

    update_data = body.model_dump(exclude_none=True)
    if "scope_type" in update_data or "project_id" in update_data:
        raise HTTPException(status_code=400, detail="变量作用域不可修改，请重新创建变量")
    if "value_encrypted" in update_data:
        update_data["value_encrypted"] = encrypt(update_data["value_encrypted"])

    for k, v in update_data.items():
        setattr(var, k, v)
    var.updated_by = current_user.id

    await db.commit()
    await db.refresh(var)
    return _serialize_variable(var)


@router.delete("/{var_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_variable(
    var_id: int,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Delete a variable."""
    var = await db.get(GlobalVariable, var_id)
    if not var:
        raise HTTPException(status_code=404, detail="Variable not found")
    if var.project_id is not None:
        await assert_project_access(db, user, var.project_id, ProjectRole.editor)
    elif user.role != UserRole.admin:
        raise HTTPException(status_code=403, detail="只有管理员可以删除全局作用域变量")
    await db.delete(var)
    await db.commit()
