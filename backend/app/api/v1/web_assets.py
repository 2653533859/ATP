"""Project-level Web locator and page-object asset APIs."""

from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import assert_project_access, get_current_user, require_engineer
from app.core.database import get_db
from app.models.project import Project
from app.models.user import User
from app.models.user_project import ProjectRole
from app.models.web_assets import WebElementAsset, WebPageObject
from app.schemas.web_assets import (
    WebElementAssetCreate,
    WebElementAssetOut,
    WebElementAssetUpdate,
    WebElementFailureIn,
    WebLocatorRepairIn,
    WebLocatorRepairOut,
    WebPageObjectCreate,
    WebPageObjectOut,
    WebPageObjectUpdate,
)
from app.services.web_locator_repair import build_locator_repair_suggestions

router = APIRouter(tags=["Web 资产"])


async def _ensure_project(db: AsyncSession, user: User, project_id: int, role: ProjectRole) -> None:
    await assert_project_access(db, user, project_id, role)
    if await db.get(Project, project_id) is None:
        raise HTTPException(status_code=404, detail="项目不存在")


@router.get("/projects/{project_id}/web-elements", response_model=list[WebElementAssetOut])
async def list_web_elements(
    project_id: int,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    await _ensure_project(db, user, project_id, ProjectRole.viewer)
    result = await db.execute(
        select(WebElementAsset)
        .where(WebElementAsset.project_id == project_id)
        .order_by(WebElementAsset.name.asc(), WebElementAsset.id.asc())
    )
    return result.scalars().all()


@router.post(
    "/projects/{project_id}/web-elements",
    response_model=WebElementAssetOut,
    status_code=status.HTTP_201_CREATED,
)
async def create_web_element(
    project_id: int,
    body: WebElementAssetCreate,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_engineer),
):
    await _ensure_project(db, user, project_id, ProjectRole.editor)
    item = WebElementAsset(project_id=project_id, owner_id=user.id, **body.model_dump())
    db.add(item)
    try:
        await db.commit()
    except Exception as exc:
        await db.rollback()
        raise HTTPException(status_code=409, detail="元素名称已存在") from exc
    await db.refresh(item)
    return item


@router.patch("/web-elements/{element_id}", response_model=WebElementAssetOut)
async def update_web_element(
    element_id: int,
    body: WebElementAssetUpdate,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_engineer),
):
    item = await db.get(WebElementAsset, element_id)
    if item is None:
        raise HTTPException(status_code=404, detail="元素资产不存在")
    await _ensure_project(db, user, item.project_id, ProjectRole.editor)
    payload = body.model_dump(exclude_unset=True)
    if payload:
        for key, value in payload.items():
            setattr(item, key, value)
        item.version += 1
    await db.commit()
    await db.refresh(item)
    return item


@router.post("/web-elements/{element_id}/failure", response_model=WebElementAssetOut)
async def record_web_element_failure(
    element_id: int,
    body: WebElementFailureIn,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_engineer),
):
    item = await db.get(WebElementAsset, element_id)
    if item is None:
        raise HTTPException(status_code=404, detail="元素资产不存在")
    await _ensure_project(db, user, item.project_id, ProjectRole.editor)
    item.last_failed_at = datetime.now(timezone.utc)
    item.last_failure_reason = body.reason
    await db.commit()
    await db.refresh(item)
    return item


@router.post("/web-elements/{element_id}/repair-preview", response_model=WebLocatorRepairOut)
async def preview_web_element_repair(
    element_id: int,
    body: WebLocatorRepairIn,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_engineer),
):
    item = await db.get(WebElementAsset, element_id)
    if item is None:
        raise HTTPException(status_code=404, detail="元素资产不存在")
    await _ensure_project(db, user, item.project_id, ProjectRole.editor)
    return WebLocatorRepairOut(
        element_id=item.id,
        candidates=build_locator_repair_suggestions(item, body.observed_locators),
    )


@router.delete("/web-elements/{element_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_web_element(
    element_id: int,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_engineer),
):
    item = await db.get(WebElementAsset, element_id)
    if item is None:
        raise HTTPException(status_code=404, detail="元素资产不存在")
    await _ensure_project(db, user, item.project_id, ProjectRole.editor)
    await db.delete(item)
    await db.commit()


@router.get("/projects/{project_id}/web-page-objects", response_model=list[WebPageObjectOut])
async def list_web_page_objects(
    project_id: int,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    await _ensure_project(db, user, project_id, ProjectRole.viewer)
    result = await db.execute(
        select(WebPageObject)
        .where(WebPageObject.project_id == project_id)
        .order_by(WebPageObject.name.asc(), WebPageObject.id.asc())
    )
    return result.scalars().all()


@router.post(
    "/projects/{project_id}/web-page-objects",
    response_model=WebPageObjectOut,
    status_code=status.HTTP_201_CREATED,
)
async def create_web_page_object(
    project_id: int,
    body: WebPageObjectCreate,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_engineer),
):
    await _ensure_project(db, user, project_id, ProjectRole.editor)
    item = WebPageObject(project_id=project_id, owner_id=user.id, **body.model_dump())
    db.add(item)
    try:
        await db.commit()
    except Exception as exc:
        await db.rollback()
        raise HTTPException(status_code=409, detail="页面对象名称已存在") from exc
    await db.refresh(item)
    return item


@router.patch("/web-page-objects/{object_id}", response_model=WebPageObjectOut)
async def update_web_page_object(
    object_id: int,
    body: WebPageObjectUpdate,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_engineer),
):
    item = await db.get(WebPageObject, object_id)
    if item is None:
        raise HTTPException(status_code=404, detail="页面对象不存在")
    await _ensure_project(db, user, item.project_id, ProjectRole.editor)
    payload = body.model_dump(exclude_unset=True)
    if payload:
        for key, value in payload.items():
            setattr(item, key, value)
        item.version += 1
    await db.commit()
    await db.refresh(item)
    return item


@router.delete("/web-page-objects/{object_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_web_page_object(
    object_id: int,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_engineer),
):
    item = await db.get(WebPageObject, object_id)
    if item is None:
        raise HTTPException(status_code=404, detail="页面对象不存在")
    await _ensure_project(db, user, item.project_id, ProjectRole.editor)
    await db.delete(item)
    await db.commit()
