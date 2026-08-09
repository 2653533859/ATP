"""CRUD for project-scoped Provider/Consumer API contract assets."""

from __future__ import annotations

from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import assert_project_access, get_current_user, require_engineer
from app.core.database import get_db
from app.models.api_contract_asset import ApiContractAsset
from app.models.project import Project
from app.models.user import User
from app.models.user_project import ProjectRole
from app.schemas.api_contract_asset import ApiContractAssetCreate, ApiContractAssetOut, ApiContractAssetUpdate

router = APIRouter(tags=["API Provider/Consumer 契约"])


async def _ensure_project(db: AsyncSession, user: User, project_id: int, role: ProjectRole) -> None:
    await assert_project_access(db, user, project_id, role)
    if await db.get(Project, project_id) is None:
        raise HTTPException(status_code=404, detail="项目不存在")


@router.get("/projects/{project_id}/api-contract-assets", response_model=list[ApiContractAssetOut])
async def list_api_contract_assets(
    project_id: int,
    role: Literal["provider", "consumer"] | None = Query(default=None),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    await _ensure_project(db, user, project_id, ProjectRole.viewer)
    query = select(ApiContractAsset).where(ApiContractAsset.project_id == project_id)
    if role is not None:
        query = query.where(ApiContractAsset.role == role)
    result = await db.execute(query.order_by(ApiContractAsset.role.asc(), ApiContractAsset.name.asc()))
    return result.scalars().all()


@router.post(
    "/projects/{project_id}/api-contract-assets",
    response_model=ApiContractAssetOut,
    status_code=status.HTTP_201_CREATED,
)
async def create_api_contract_asset(
    project_id: int,
    body: ApiContractAssetCreate,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_engineer),
):
    await _ensure_project(db, user, project_id, ProjectRole.editor)
    item = ApiContractAsset(project_id=project_id, owner_id=user.id, **body.model_dump())
    db.add(item)
    try:
        await db.commit()
    except IntegrityError as exc:
        await db.rollback()
        raise HTTPException(status_code=409, detail="同一 Provider/Consumer 下契约名称已存在") from exc
    await db.refresh(item)
    return item


@router.patch("/api-contract-assets/{asset_id}", response_model=ApiContractAssetOut)
async def update_api_contract_asset(
    asset_id: int,
    body: ApiContractAssetUpdate,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_engineer),
):
    item = await db.get(ApiContractAsset, asset_id)
    if item is None:
        raise HTTPException(status_code=404, detail="契约资产不存在")
    await _ensure_project(db, user, item.project_id, ProjectRole.editor)
    changes = body.model_dump(exclude_unset=True)
    for key, value in changes.items():
        setattr(item, key, value)
    if changes:
        item.version += 1
    try:
        await db.commit()
    except IntegrityError as exc:
        await db.rollback()
        raise HTTPException(status_code=409, detail="同一 Provider/Consumer 下契约名称已存在") from exc
    await db.refresh(item)
    return item


@router.delete("/api-contract-assets/{asset_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_api_contract_asset(
    asset_id: int,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_engineer),
):
    item = await db.get(ApiContractAsset, asset_id)
    if item is None:
        raise HTTPException(status_code=404, detail="契约资产不存在")
    await _ensure_project(db, user, item.project_id, ProjectRole.editor)
    await db.delete(item)
    await db.commit()
