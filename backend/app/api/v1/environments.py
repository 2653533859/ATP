from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select, delete
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.models.environment import Environment, EnvVariable
from app.schemas.environment import (
    EnvironmentCreate,
    EnvironmentUpdate,
    EnvironmentOut,
    EnvVariableBatchSave,
    EnvVariableOut,
)
from app.api.deps import get_current_user

router = APIRouter(tags=["环境管理"])


@router.get("/environments", response_model=list[EnvironmentOut])
async def list_environments(
    project_id: int = Query(..., description="项目 ID"),
    db: AsyncSession = Depends(get_db),
    _=Depends(get_current_user),
):
    result = await db.execute(
        select(Environment)
        .where(Environment.project_id == project_id)
        .order_by(Environment.created_at.desc())
    )
    return result.scalars().all()


@router.post("/environments", response_model=EnvironmentOut, status_code=status.HTTP_201_CREATED)
async def create_environment(
    body: EnvironmentCreate,
    db: AsyncSession = Depends(get_db),
    _=Depends(get_current_user),
):
    env = Environment(**body.model_dump())
    db.add(env)
    await db.commit()
    await db.refresh(env)
    return env


@router.patch("/environments/{env_id}", response_model=EnvironmentOut)
async def update_environment(
    env_id: int,
    body: EnvironmentUpdate,
    db: AsyncSession = Depends(get_db),
    _=Depends(get_current_user),
):
    env = await db.get(Environment, env_id)
    if not env:
        raise HTTPException(status_code=404, detail="环境不存在")
    for k, v in body.model_dump(exclude_none=True).items():
        setattr(env, k, v)
    await db.commit()
    await db.refresh(env)
    return env


@router.delete("/environments/{env_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_environment(
    env_id: int,
    db: AsyncSession = Depends(get_db),
    _=Depends(get_current_user),
):
    env = await db.get(Environment, env_id)
    if not env:
        raise HTTPException(status_code=404, detail="环境不存在")
    await db.delete(env)
    await db.commit()


@router.get("/environments/{env_id}/variables", response_model=list[EnvVariableOut])
async def get_variables(
    env_id: int,
    db: AsyncSession = Depends(get_db),
    _=Depends(get_current_user),
):
    env = await db.get(Environment, env_id)
    if not env:
        raise HTTPException(status_code=404, detail="环境不存在")
    result = await db.execute(
        select(EnvVariable).where(EnvVariable.env_id == env_id)
    )
    variables = result.scalars().all()
    return [_mask_variable(v) for v in variables]


@router.put("/environments/{env_id}/variables", response_model=list[EnvVariableOut])
async def save_variables(
    env_id: int,
    body: EnvVariableBatchSave,
    db: AsyncSession = Depends(get_db),
    _=Depends(get_current_user),
):
    env = await db.get(Environment, env_id)
    if not env:
        raise HTTPException(status_code=404, detail="环境不存在")

    # Bulk delete existing variables
    await db.execute(
        delete(EnvVariable).where(EnvVariable.env_id == env_id)
    )

    # Insert new variables
    new_vars = []
    for item in body.variables:
        var = EnvVariable(env_id=env_id, **item.model_dump())
        db.add(var)
        new_vars.append(var)

    await db.commit()
    for var in new_vars:
        await db.refresh(var)

    return [_mask_variable(v) for v in new_vars]


def _mask_variable(var: EnvVariable) -> EnvVariableOut:
    return EnvVariableOut(
        id=var.id,
        key=var.key,
        value="******" if var.is_secret else var.value,
        is_secret=var.is_secret,
    )
