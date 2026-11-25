"""项目级对象存储文件资产（API multipart 文件 / Web 上传文件）共用查询、重命名与删除逻辑。"""

from __future__ import annotations

import asyncio
import mimetypes
from collections.abc import Callable
from datetime import datetime

from fastapi import HTTPException
from pydantic import BaseModel, Field

from app.core.minio_client import delete_file, ensure_bucket, list_objects, read_bytes, upload_bytes


class ProjectFileAssetOut(BaseModel):
    object_name: str
    filename: str
    size: int = 0
    last_modified: datetime | None = None


class ProjectFileRenameIn(BaseModel):
    object_name: str = Field(..., min_length=1, max_length=512)
    filename: str = Field(..., min_length=1, max_length=255)


class ProjectFileRenameOut(BaseModel):
    old_object_name: str
    object_name: str
    filename: str
    content_type: str
    size: int


def _project_prefix(namespace: str, project_id: int) -> str:
    return f"{namespace}/projects/{project_id}/"


def validate_project_object_name(namespace: str, project_id: int, object_name: str) -> str:
    """校验对象路径必须位于指定项目前缀下且不包含路径穿越片段。"""
    cleaned = (object_name or "").strip().lstrip("/")
    prefix = _project_prefix(namespace, project_id)
    if (
        not cleaned
        or "\x00" in cleaned
        or "\\" in cleaned
        or not cleaned.startswith(prefix)
        or len(cleaned) <= len(prefix)
        or any(part in {"", ".", ".."} for part in cleaned.split("/"))
    ):
        raise HTTPException(status_code=400, detail="非法的项目文件对象路径")
    return cleaned


def extract_filename_from_object_name(object_name: str) -> str:
    basename = object_name.rsplit("/", 1)[-1]
    head, sep, tail = basename.partition("_")
    if sep and len(head) == 32 and all(ch in "0123456789abcdefABCDEF" for ch in head) and tail:
        return tail
    return basename


def _read_existing_bytes(object_name: str) -> bytes:
    try:
        return read_bytes(object_name)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail="文件不存在") from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="非法的项目文件对象路径") from exc
    except Exception as exc:
        if getattr(exc, "code", None) in {"NoSuchKey", "NoSuchObject", "NoSuchBucket"}:
            raise HTTPException(status_code=404, detail="文件不存在") from exc
        raise


def _object_exists(object_name: str) -> bool:
    ensure_bucket()
    return any(getattr(item, "object_name", "") == object_name for item in list_objects(object_name))


async def list_project_files(namespace: str, project_id: int) -> list[ProjectFileAssetOut]:
    prefix = _project_prefix(namespace, project_id)

    def _collect() -> list[ProjectFileAssetOut]:
        ensure_bucket()
        items: list[ProjectFileAssetOut] = []
        for obj in list_objects(prefix):
            name = str(getattr(obj, "object_name", "") or "")
            if not name.startswith(prefix) or len(name) <= len(prefix):
                continue
            items.append(
                ProjectFileAssetOut(
                    object_name=name,
                    filename=extract_filename_from_object_name(name),
                    size=int(getattr(obj, "size", 0) or 0),
                    last_modified=getattr(obj, "last_modified", None),
                )
            )
        items.sort(
            key=lambda item: (item.last_modified.isoformat() if item.last_modified else "", item.object_name),
            reverse=True,
        )
        return items

    return await asyncio.to_thread(_collect)


async def rename_project_file(
    namespace: str,
    project_id: int,
    object_name: str,
    new_filename: str,
    build_object_name: Callable[[int, str], str],
) -> ProjectFileRenameOut:
    old_name = validate_project_object_name(namespace, project_id, object_name)
    cleaned_filename = new_filename.strip()
    if not cleaned_filename or "/" in cleaned_filename or "\\" in cleaned_filename or cleaned_filename in {".", ".."}:
        raise HTTPException(status_code=400, detail="非法的文件名")
    new_object_name = build_object_name(project_id, cleaned_filename)

    def _move() -> tuple[bytes, str]:
        ensure_bucket()
        data = _read_existing_bytes(old_name)
        content_type = (
            mimetypes.guess_type(cleaned_filename)[0]
            or mimetypes.guess_type(new_object_name)[0]
            or "application/octet-stream"
        )
        upload_bytes(new_object_name, data, content_type=content_type)
        delete_file(old_name)
        return data, content_type

    data, content_type = await asyncio.to_thread(_move)
    return ProjectFileRenameOut(
        old_object_name=old_name,
        object_name=new_object_name,
        filename=extract_filename_from_object_name(new_object_name),
        content_type=content_type,
        size=len(data),
    )


async def delete_project_file(namespace: str, project_id: int, object_name: str) -> None:
    target = validate_project_object_name(namespace, project_id, object_name)

    def _remove() -> None:
        if not _object_exists(target):
            raise HTTPException(status_code=404, detail="文件不存在")
        delete_file(target)

    await asyncio.to_thread(_remove)
