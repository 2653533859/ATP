"""Web 用例上传/下载动作使用的项目级文件资产。"""

from __future__ import annotations

import os
import re
import tempfile
import uuid

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import assert_project_access, require_engineer
from app.core.database import get_db
from app.core.minio_client import ensure_bucket, upload_file
from app.models.user import User
from app.models.user_project import ProjectRole

router = APIRouter(tags=["Web 文件"])

_MAX_WEB_FILE_SIZE = 20 * 1024 * 1024
_CHUNK_SIZE = 1024 * 1024
_SAFE_FILENAME = re.compile(r"[^A-Za-z0-9._-]+")


def _object_name(project_id: int, filename: str) -> str:
    safe_name = _SAFE_FILENAME.sub("_", filename or "upload.bin").strip("._") or "upload.bin"
    return f"web-files/projects/{project_id}/{uuid.uuid4().hex}_{safe_name}"


async def _save_upload(file: UploadFile) -> tuple[str, int]:
    temp = tempfile.NamedTemporaryFile(prefix="web-file-", suffix=".upload", delete=False)
    temp_path = temp.name
    total = 0
    try:
        with temp:
            while True:
                chunk = await file.read(_CHUNK_SIZE)
                if not chunk:
                    break
                total += len(chunk)
                if total > _MAX_WEB_FILE_SIZE:
                    raise HTTPException(status_code=413, detail="Web 文件超过 20MB 限制")
                temp.write(chunk)
        return temp_path, total
    except Exception:
        try:
            os.remove(temp_path)
        except OSError:
            pass
        raise


@router.post("/projects/{project_id}/web-files")
async def upload_web_file(
    project_id: int,
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_engineer),
):
    """上传供 Web 低代码上传动作引用的文件，返回项目隔离的对象引用。"""
    await assert_project_access(db, current_user, project_id, ProjectRole.editor)
    filename = file.filename or "upload.bin"
    temp_path = ""
    try:
        temp_path, size = await _save_upload(file)
        object_name = _object_name(project_id, filename)
        ensure_bucket()
        upload_file(object_name, temp_path, content_type=file.content_type or "application/octet-stream")
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
