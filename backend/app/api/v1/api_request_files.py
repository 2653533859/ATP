"""API 用例 multipart 请求文件管理。"""

from __future__ import annotations

import asyncio
import os
import re
import tempfile
import uuid

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import assert_project_access, get_current_user
from app.core.database import get_db
from app.core.minio_client import ensure_bucket, upload_file
from app.models.user import User
from app.models.user_project import ProjectRole
from app.services.project_file_assets import (
    ProjectFileAssetOut,
    ProjectFileRenameIn,
    ProjectFileRenameOut,
    delete_project_file,
    list_project_files,
    rename_project_file,
)

router = APIRouter(tags=["API 请求文件"])

_MAX_REQUEST_FILE_SIZE = 20 * 1024 * 1024
_CHUNK_SIZE = 1024 * 1024
_SAFE_FILENAME = re.compile(r"[^A-Za-z0-9._-]+")


def _object_name(project_id: int, filename: str) -> str:
    safe_name = _SAFE_FILENAME.sub("_", filename or "upload.bin").strip("._") or "upload.bin"
    return f"api-files/projects/{project_id}/{uuid.uuid4().hex}_{safe_name}"


async def _save_upload(file: UploadFile) -> tuple[str, int]:
    temp = tempfile.NamedTemporaryFile(prefix="api-request-file-", suffix=".upload", delete=False)
    temp_path = temp.name
    total = 0
    try:
        with temp:
            while True:
                chunk = await file.read(_CHUNK_SIZE)
                if not chunk:
                    break
                total += len(chunk)
                if total > _MAX_REQUEST_FILE_SIZE:
                    raise HTTPException(status_code=413, detail="API 请求文件超过 20MB 限制")
                temp.write(chunk)
        return temp_path, total
    except Exception:
        try:
            os.remove(temp_path)
        except OSError:
            pass
        raise


@router.post("/projects/{project_id}/api-request-files")
async def upload_api_request_file(
    project_id: int,
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """上传 API multipart 文件，返回可写入用例 config 的对象引用。"""
    await assert_project_access(db, current_user, project_id, ProjectRole.editor)
    filename = file.filename or "upload.bin"
    temp_path = ""
    try:
        temp_path, size = await _save_upload(file)
        object_name = _object_name(project_id, filename)
        await asyncio.to_thread(ensure_bucket)
        await asyncio.to_thread(
            upload_file, object_name, temp_path, content_type=file.content_type or "application/octet-stream"
        )
    finally:
        if temp_path:
            try:
                os.remove(temp_path)
            except OSError:
                pass
        await file.close()

    return {
        "object_name": object_name,
        "filename": filename,
        "content_type": file.content_type or "application/octet-stream",
        "size": size,
    }


@router.get("/projects/{project_id}/api-request-files", response_model=list[ProjectFileAssetOut])
async def list_api_request_files(
    project_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> list[ProjectFileAssetOut]:
    """列出项目下已上传的 API 请求文件资产。"""
    await assert_project_access(db, current_user, project_id, ProjectRole.viewer)
    return await list_project_files("api-files", project_id)


@router.patch("/projects/{project_id}/api-request-files", response_model=ProjectFileRenameOut)
async def rename_api_request_file(
    project_id: int,
    body: ProjectFileRenameIn,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> ProjectFileRenameOut:
    """重命名项目下的 API 请求文件（生成新对象名并清理旧对象）。"""
    await assert_project_access(db, current_user, project_id, ProjectRole.editor)
    return await rename_project_file("api-files", project_id, body.object_name, body.filename, _object_name)


@router.delete("/projects/{project_id}/api-request-files", status_code=status.HTTP_204_NO_CONTENT)
async def remove_api_request_file(
    project_id: int,
    object_name: str = Query(..., min_length=1),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> None:
    """删除项目下已上传的 API 请求文件资产。"""
    await assert_project_access(db, current_user, project_id, ProjectRole.editor)
    await delete_project_file("api-files", project_id, object_name)
