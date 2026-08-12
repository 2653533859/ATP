"""Shared validation and MinIO reference storage for test datasets."""

from __future__ import annotations

import json
import logging
from typing import Any
from uuid import uuid4

from app.core import minio_client

logger = logging.getLogger(__name__)

MAX_DATASET_ROWS = 500
MAX_DATASET_ROWS_BYTES = 256 * 1024
MAX_DATASET_OBJECT_BYTES = 50 * 1024 * 1024
DATASET_STORAGE_DATABASE = "database"
DATASET_STORAGE_MINIO = "minio"
MAX_RECONCILE_REPORT_OBJECTS = 1_000


class DatasetStorageLimitError(ValueError):
    """Raised when dataset rows exceed the selected storage limits."""


class DatasetStorageError(ValueError):
    """Raised when a MinIO-backed dataset cannot be decoded or addressed."""


def serialize_dataset_rows(rows: list[dict[str, Any]]) -> bytes:
    return json.dumps(rows, ensure_ascii=False, separators=(",", ":")).encode("utf-8")


def validate_dataset_rows_size(rows: list[dict], storage_mode: str = DATASET_STORAGE_DATABASE) -> None:
    serialized_size = len(serialize_dataset_rows(rows))
    if storage_mode == DATASET_STORAGE_MINIO:
        if serialized_size > MAX_DATASET_OBJECT_BYTES:
            raise DatasetStorageLimitError(
                f"数据集对象超过 {MAX_DATASET_OBJECT_BYTES // 1024 // 1024}MB 上限；请拆分数据集"
            )
        return
    if storage_mode != DATASET_STORAGE_DATABASE:
        raise DatasetStorageLimitError("数据集存储模式仅支持 database 或 minio")
    if len(rows) > MAX_DATASET_ROWS:
        raise DatasetStorageLimitError(f"行数超过 {MAX_DATASET_ROWS} 上限；请改用 MinIO 引用模式")
    if serialized_size > MAX_DATASET_ROWS_BYTES:
        raise DatasetStorageLimitError(f"序列化后超过 {MAX_DATASET_ROWS_BYTES // 1024}KB；请改用 MinIO 引用模式")


def dataset_object_name(project_id: int, dataset_id: int, version: int | None = None) -> str:
    suffix = "current" if version is None else f"version-{version}"
    return f"datasets/{project_id}/{dataset_id}/{suffix}.json"


def dataset_current_object_name(project_id: int, dataset_id: int) -> str:
    """Return a unique current-object name for transactional replacements."""
    return f"datasets/{project_id}/{dataset_id}/current-{uuid4().hex}.json"


def dataset_project_prefix(project_id: int) -> str:
    """Return the only MinIO prefix that may be reconciled for a project."""
    return f"datasets/{project_id}/"


def upload_dataset_rows(
    *,
    project_id: int,
    dataset_id: int,
    rows: list[dict[str, Any]],
    version: int | None = None,
    object_name: str | None = None,
) -> str:
    validate_dataset_rows_size(rows, DATASET_STORAGE_MINIO)
    object_name = object_name or dataset_object_name(project_id, dataset_id, version)
    try:
        minio_client.upload_bytes(object_name, serialize_dataset_rows(rows), content_type="application/json")
    except Exception as exc:
        raise DatasetStorageError(f"上传 MinIO 数据集失败: {exc}") from exc
    return object_name


def read_dataset_rows(object_name: str | None) -> list[dict[str, Any]]:
    if not object_name:
        raise DatasetStorageError("MinIO 数据集缺少对象引用")
    try:
        payload = json.loads(minio_client.read_bytes(object_name).decode("utf-8"))
    except Exception as exc:
        raise DatasetStorageError(f"读取 MinIO 数据集失败: {exc}") from exc
    if not isinstance(payload, list) or not all(isinstance(row, dict) for row in payload):
        raise DatasetStorageError("MinIO 数据集对象必须是对象数组")
    return payload


def rows_from_source(source: Any) -> list[dict[str, Any]]:
    if source is None:
        return []
    if getattr(source, "storage_mode", DATASET_STORAGE_DATABASE) == DATASET_STORAGE_MINIO:
        return read_dataset_rows(getattr(source, "object_name", None))
    return [row for row in (getattr(source, "rows", None) or []) if isinstance(row, dict)]


def delete_dataset_objects(project_id: int, dataset_id: int) -> int:
    """Delete current and immutable version objects after a dataset is removed."""
    prefix = f"{dataset_project_prefix(project_id)}{dataset_id}/"
    deleted = 0
    for item in minio_client.list_objects(prefix=prefix):
        object_name = getattr(item, "object_name", None) or str(item)
        if object_name.startswith(prefix):
            minio_client.delete_file(object_name)
            deleted += 1
    return deleted


def cleanup_dataset_object_names(project_id: int, dataset_id: int, object_names: list[str]) -> list[str]:
    """Best-effort cleanup for objects uploaded before a failed DB transaction."""
    prefix = f"{dataset_project_prefix(project_id)}{dataset_id}/"
    errors: list[str] = []
    for object_name in dict.fromkeys(object_names):
        if not object_name.startswith(prefix):
            errors.append(f"{object_name}: object is outside dataset prefix")
            continue
        try:
            minio_client.delete_file(object_name)
        except Exception as exc:
            error = f"{object_name}: {exc}"
            errors.append(error)
            logger.warning("Failed to clean up MinIO dataset object after rollback: %s", error)
    return errors


def reconcile_dataset_objects(
    project_id: int,
    referenced_object_names: set[str],
    *,
    purge: bool = False,
) -> dict[str, Any]:
    """Compare project-scoped MinIO objects with database references.

    The default is a dry run. Deletion is opt-in and remains limited to the
    exact project prefix, so a stale or malformed database reference cannot
    cause an unrelated bucket object to be removed.
    """
    prefix = dataset_project_prefix(project_id)
    try:
        listed_names = {
            object_name
            for item in minio_client.list_objects(prefix=prefix)
            for object_name in [getattr(item, "object_name", None) or str(item)]
            if isinstance(object_name, str) and object_name.startswith(prefix)
        }
    except Exception as exc:
        raise DatasetStorageError(f"MinIO 数据集对象清单读取失败: {exc}") from exc

    scoped_references = {
        object_name
        for object_name in referenced_object_names
        if isinstance(object_name, str) and object_name.startswith(prefix)
    }
    orphaned_names = sorted(listed_names - scoped_references)
    deleted_count = 0
    errors: list[str] = []
    if purge:
        for object_name in orphaned_names:
            try:
                minio_client.delete_file(object_name)
                deleted_count += 1
            except Exception as exc:
                errors.append(f"{object_name}: {exc}")

    return {
        "project_id": project_id,
        "dry_run": not purge,
        "scanned_count": len(listed_names),
        "referenced_count": len(scoped_references),
        "orphan_count": len(orphaned_names),
        "orphaned_objects": orphaned_names[:MAX_RECONCILE_REPORT_OBJECTS],
        "truncated": len(orphaned_names) > MAX_RECONCILE_REPORT_OBJECTS,
        "deleted_count": deleted_count,
        "errors": errors,
    }
