"""Project-scoped JSON Schema asset CRUD."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import assert_project_access, get_current_user, require_engineer
from app.core.database import get_db
from app.models.api_schema import ApiSchemaAsset
from app.models.project import Project
from app.models.user import User
from app.models.user_project import ProjectRole
from app.schemas.api_schema import ApiSchemaAssetCreate, ApiSchemaAssetOut, ApiSchemaAssetUpdate

router = APIRouter(tags=["API Schema 资产"])


async def _ensure_project(db: AsyncSession, user: User, project_id: int, role: ProjectRole) -> None:
    await assert_project_access(db, user, project_id, role)
    if await db.get(Project, project_id) is None:
        raise HTTPException(status_code=404, detail="项目不存在")


@router.get("/projects/{project_id}/api-schema-assets", response_model=list[ApiSchemaAssetOut])
async def list_api_schema_assets(
    project_id: int,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    await _ensure_project(db, user, project_id, ProjectRole.viewer)
    result = await db.execute(
        select(ApiSchemaAsset)
        .where(ApiSchemaAsset.project_id == project_id)
        .order_by(ApiSchemaAsset.name.asc(), ApiSchemaAsset.id.asc())
    )
    return result.scalars().all()


@router.post(
    "/projects/{project_id}/api-schema-assets",
    response_model=ApiSchemaAssetOut,
    status_code=status.HTTP_201_CREATED,
)
async def create_api_schema_asset(
    project_id: int,
    body: ApiSchemaAssetCreate,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_engineer),
):
    await _ensure_project(db, user, project_id, ProjectRole.editor)
    item = ApiSchemaAsset(project_id=project_id, owner_id=user.id, **body.model_dump())
    db.add(item)
    try:
        await db.commit()
    except IntegrityError as exc:
        await db.rollback()
        raise HTTPException(status_code=409, detail="Schema 资产名称已存在") from exc
    await db.refresh(item)
    return item


@router.patch("/api-schema-assets/{asset_id}", response_model=ApiSchemaAssetOut)
async def update_api_schema_asset(
    asset_id: int,
    body: ApiSchemaAssetUpdate,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_engineer),
):
    item = await db.get(ApiSchemaAsset, asset_id)
    if item is None:
        raise HTTPException(status_code=404, detail="Schema 资产不存在")
    await _ensure_project(db, user, item.project_id, ProjectRole.editor)
    for key, value in body.model_dump(exclude_unset=True).items():
        setattr(item, key, value)
    if body.model_dump(exclude_unset=True):
        item.version += 1
    try:
        await db.commit()
    except IntegrityError as exc:
        await db.rollback()
        raise HTTPException(status_code=409, detail="Schema 资产名称已存在") from exc
    await db.refresh(item)
    return item


@router.delete("/api-schema-assets/{asset_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_api_schema_asset(
    asset_id: int,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_engineer),
):
    item = await db.get(ApiSchemaAsset, asset_id)
    if item is None:
        raise HTTPException(status_code=404, detail="Schema 资产不存在")
    await _ensure_project(db, user, item.project_id, ProjectRole.editor)
    await db.delete(item)
    await db.commit()
