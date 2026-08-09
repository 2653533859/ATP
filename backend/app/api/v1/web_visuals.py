"""Web visual baseline assets and project-scoped image upload API."""

from __future__ import annotations

import json
import re
import uuid
from io import BytesIO

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status
from PIL import Image
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import assert_project_access, get_current_user, require_engineer
from app.core.database import get_db
from app.core.minio_client import delete_file, ensure_bucket, upload_bytes
from app.models.project import Project
from app.models.user import User
from app.models.user_project import ProjectRole
from app.models.web_assets import WebVisualBaseline
from app.schemas.web_visuals import WebVisualBaselineOut, WebVisualBaselineSettings

router = APIRouter(tags=["Web 视觉回归"])

_MAX_VISUAL_FILE_SIZE = 10 * 1024 * 1024
_SAFE_NAME = re.compile(r"[^A-Za-z0-9._-]+")


async def _ensure_project(db: AsyncSession, user: User, project_id: int, role: ProjectRole) -> None:
    await assert_project_access(db, user, project_id, role)
    if await db.get(Project, project_id) is None:
        raise HTTPException(status_code=404, detail="项目不存在")


def _parse_regions(raw: str) -> list[dict]:
    try:
        value = json.loads(raw or "[]")
    except json.JSONDecodeError as exc:
        raise HTTPException(status_code=422, detail="忽略区域必须是合法 JSON 数组") from exc
    if not isinstance(value, list) or len(value) > 100:
        raise HTTPException(status_code=422, detail="忽略区域必须是最多 100 项的数组")
    return [item for item in value if isinstance(item, dict)]


@router.get("/projects/{project_id}/web-visual-baselines", response_model=list[WebVisualBaselineOut])
async def list_web_visual_baselines(
    project_id: int,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    await _ensure_project(db, user, project_id, ProjectRole.viewer)
    result = await db.execute(
        select(WebVisualBaseline)
        .where(WebVisualBaseline.project_id == project_id)
        .order_by(WebVisualBaseline.name.asc(), WebVisualBaseline.id.asc())
    )
    return result.scalars().all()


@router.post(
    "/projects/{project_id}/web-visual-baselines",
    response_model=WebVisualBaselineOut,
    status_code=status.HTTP_201_CREATED,
)
async def upload_web_visual_baseline(
    project_id: int,
    name: str = Form(..., min_length=1, max_length=128),
    page_url: str | None = Form(default=None),
    threshold: float = Form(default=0.01, ge=0, le=1),
    pixel_threshold: int = Form(default=10, ge=0, le=255),
    ignore_regions: str = Form(default="[]"),
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_engineer),
):
    await _ensure_project(db, user, project_id, ProjectRole.editor)
    data = await file.read(_MAX_VISUAL_FILE_SIZE + 1)
    await file.close()
    if len(data) > _MAX_VISUAL_FILE_SIZE:
        raise HTTPException(status_code=413, detail="视觉基线超过 10MB 限制")
    try:
        image = Image.open(BytesIO(data))
        image.load()
    except Exception as exc:
        raise HTTPException(status_code=422, detail="视觉基线必须是有效图片") from exc
    if image.format != "PNG":
        raise HTTPException(status_code=422, detail="视觉基线仅支持 PNG")
    regions = _parse_regions(ignore_regions)
    safe_name = _SAFE_NAME.sub("_", name).strip("._") or "baseline"
    object_name = f"visual-baselines/projects/{project_id}/{uuid.uuid4().hex}_{safe_name}.png"
    ensure_bucket()
    upload_bytes(object_name, data, content_type="image/png")
    item = WebVisualBaseline(
        project_id=project_id,
        name=name.strip(),
        page_url=page_url,
        object_name=object_name,
        content_type="image/png",
        width=image.width,
        height=image.height,
        threshold=threshold,
        pixel_threshold=pixel_threshold,
        ignore_regions=regions,
        version=1,
        owner_id=user.id,
    )
    db.add(item)
    try:
        await db.commit()
    except Exception as exc:
        await db.rollback()
        delete_file(object_name)
        raise HTTPException(status_code=409, detail="视觉基线名称已存在") from exc
    await db.refresh(item)
    return item


@router.patch("/web-visual-baselines/{baseline_id}", response_model=WebVisualBaselineOut)
async def update_web_visual_baseline(
    baseline_id: int,
    body: WebVisualBaselineSettings,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_engineer),
):
    item = await db.get(WebVisualBaseline, baseline_id)
    if item is None:
        raise HTTPException(status_code=404, detail="视觉基线不存在")
    await _ensure_project(db, user, item.project_id, ProjectRole.editor)
    item.threshold = body.threshold
    item.pixel_threshold = body.pixel_threshold
    item.ignore_regions = body.ignore_regions
    item.version += 1
    await db.commit()
    await db.refresh(item)
    return item


@router.delete("/web-visual-baselines/{baseline_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_web_visual_baseline(
    baseline_id: int,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_engineer),
):
    item = await db.get(WebVisualBaseline, baseline_id)
    if item is None:
        raise HTTPException(status_code=404, detail="视觉基线不存在")
    await _ensure_project(db, user, item.project_id, ProjectRole.editor)
    object_name = item.object_name
    await db.delete(item)
    await db.commit()
    try:
        delete_file(object_name)
    except Exception:
        pass
