"""
APK 管理 API

POST   /apks                上传 APK 文件（multipart/form-data）
GET    /apks                APK 列表（支持 project_id 过滤）
GET    /apks/{apk_id}       APK 详情
PATCH  /apks/{apk_id}       更新 APK 信息
DELETE /apks/{apk_id}       删除 APK
GET    /apks/{apk_id}/download  获取 APK 下载链接
"""

import os
import tempfile
import uuid

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form, Query, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.minio_client import ensure_bucket, upload_file, presigned_url, delete_file
from app.models.apk import Apk
from app.models.project import Project
from app.models.user import User
from app.schemas.apk import ApkOut, ApkUpdate
from app.api.deps import assert_project_access, get_current_user, require_engineer
from app.models.user_project import ProjectRole

router = APIRouter(tags=["APK 管理"])

_MAX_APK_SIZE = 500 * 1024 * 1024  # 500 MB
_UPLOAD_CHUNK_SIZE = 1024 * 1024  # 1 MB


def _apk_object_name(project_id: int, filename: str) -> str:
    short_id = uuid.uuid4().hex[:8]
    return f"apks/projects/{project_id}/{short_id}_{filename}"


async def _save_upload_to_tempfile(
    file: UploadFile,
    max_size: int = _MAX_APK_SIZE,
    chunk_size: int = _UPLOAD_CHUNK_SIZE,
) -> tuple[str, int]:
    """分块读取上传文件到临时文件，返回 (temp_path, file_size)。"""
    temp = tempfile.NamedTemporaryFile(prefix="apk-upload-", suffix=".apk", delete=False)
    temp_path = temp.name
    total_size = 0

    try:
        with temp:
            while True:
                chunk = await file.read(chunk_size)
                if not chunk:
                    break
                total_size += len(chunk)
                if total_size > max_size:
                    raise HTTPException(status_code=413, detail="APK 文件超过 500MB 限制")
                temp.write(chunk)
        return temp_path, total_size
    except Exception:
        try:
            os.remove(temp_path)
        except OSError:
            pass
        raise


@router.post("/apks", response_model=ApkOut, status_code=status.HTTP_201_CREATED)
async def upload_apk(
    project_id: int = Form(...),
    file: UploadFile = File(...),
    package_name: str | None = Form(None),
    version_name: str | None = Form(None),
    version_code: int | None = Form(None),
    description: str | None = Form(None),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_engineer),
):
    """上传 APK 文件到 MinIO 并创建记录"""
    # 校验项目存在
    await assert_project_access(db, current_user, project_id, ProjectRole.editor)
    project = await db.get(Project, project_id)
    if not project:
        raise HTTPException(status_code=404, detail="项目不存在")

    # 校验文件类型
    filename = file.filename or "unknown.apk"
    if not filename.lower().endswith(".apk"):
        raise HTTPException(status_code=400, detail="仅支持 .apk 文件")

    temp_path = ""
    file_size = 0
    object_name = _apk_object_name(project_id, filename)
    try:
        temp_path, file_size = await _save_upload_to_tempfile(file, max_size=_MAX_APK_SIZE)
        ensure_bucket()
        upload_file(
            object_name,
            temp_path,
            content_type="application/vnd.android.package-archive",
        )
    finally:
        if temp_path:
            try:
                os.remove(temp_path)
            except OSError:
                pass
        await file.close()

    apk = Apk(
        project_id=project_id,
        filename=filename,
        package_name=package_name,
        version_name=version_name,
        version_code=version_code,
        file_size=file_size,
        object_name=object_name,
        description=description,
        uploaded_by=current_user.id,
    )
    db.add(apk)
    await db.commit()
    await db.refresh(apk)
    return apk


@router.get("/apks", response_model=list[ApkOut])
async def list_apks(
    project_id: int | None = Query(None),
    db: AsyncSession = Depends(get_db),
    user=Depends(get_current_user),
):
    if project_id is not None:
        await assert_project_access(db, user, project_id, ProjectRole.viewer)
    q = select(Apk).order_by(Apk.created_at.desc())
    if project_id is not None:
        q = q.where(Apk.project_id == project_id)
    result = await db.execute(q)
    return result.scalars().all()


@router.get("/apks/{apk_id}", response_model=ApkOut)
async def get_apk(
    apk_id: int,
    db: AsyncSession = Depends(get_db),
    user=Depends(get_current_user),
):
    apk = await db.get(Apk, apk_id)
    if not apk:
        raise HTTPException(status_code=404, detail="APK 不存在")
    await assert_project_access(db, user, apk.project_id, ProjectRole.viewer)
    return apk


@router.patch("/apks/{apk_id}", response_model=ApkOut)
async def update_apk(
    apk_id: int,
    body: ApkUpdate,
    db: AsyncSession = Depends(get_db),
    user=Depends(require_engineer),
):
    apk = await db.get(Apk, apk_id)
    if not apk:
        raise HTTPException(status_code=404, detail="APK 不存在")
    await assert_project_access(db, user, apk.project_id, ProjectRole.editor)
    for k, v in body.model_dump(exclude_none=True).items():
        setattr(apk, k, v)
    await db.commit()
    await db.refresh(apk)
    return apk


@router.delete("/apks/{apk_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_apk(
    apk_id: int,
    db: AsyncSession = Depends(get_db),
    user=Depends(require_engineer),
):
    apk = await db.get(Apk, apk_id)
    if not apk:
        raise HTTPException(status_code=404, detail="APK 不存在")
    await assert_project_access(db, user, apk.project_id, ProjectRole.editor)
    # 删除 MinIO 中的文件
    try:
        delete_file(apk.object_name)
    except Exception:
        pass
    await db.delete(apk)
    await db.commit()


@router.get("/apks/{apk_id}/download")
async def download_apk(
    apk_id: int,
    db: AsyncSession = Depends(get_db),
    user=Depends(get_current_user),
):
    """获取 APK 预签名下载链接"""
    apk = await db.get(Apk, apk_id)
    if not apk:
        raise HTTPException(status_code=404, detail="APK 不存在")
    await assert_project_access(db, user, apk.project_id, ProjectRole.viewer)
    url = presigned_url(apk.object_name, expires_seconds=3600)
    return {"url": url, "filename": apk.filename}
