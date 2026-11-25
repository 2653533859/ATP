import asyncio
import mimetypes
import re
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import Response
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import assert_project_access, get_current_user, require_admin, require_engineer
from app.core.database import get_db
from app.models.case import TestCase, TestRun
from app.models.mobile_special import MobileSpecialRun, MobileSpecialTask
from app.models.performance import PerformanceRun
from app.models.project import Module
from app.models.storage_policy import StoragePolicy
from app.models.user import User, UserRole
from app.models.user_project import ProjectRole
from app.schemas.storage import (
    StorageCleanupExecuteIn,
    StorageCleanupExecuteOut,
    StorageCleanupPreviewIn,
    StorageCleanupPreviewOut,
    StorageStatsOut,
)
from app.schemas.storage_policy import (
    StoragePolicyCreateIn,
    StoragePolicyOut,
    StoragePolicyUpdateIn,
)
from app.services.storage_alerts import get_current_alert
from app.services.storage_cleanup import (
    execute_storage_cleanup,
    get_storage_stats,
    load_active_policies,
    preview_storage_cleanup,
)

router = APIRouter(tags=["存储治理"])


def _normalize_prefix(value: str) -> str:
    prefix = (value or "").strip().lstrip("/")
    if not prefix:
        raise HTTPException(status_code=400, detail="prefix 不能为空")
    if not prefix.endswith("/"):
        prefix = f"{prefix}/"
    return prefix


@router.get("/storage/stats", response_model=StorageStatsOut)
async def storage_stats(
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_admin),
):
    stats = await db.run_sync(lambda session: get_storage_stats(session))
    try:
        from app.core.metrics import STORAGE_TOTAL_BYTES, STORAGE_TOTAL_OBJECTS

        STORAGE_TOTAL_BYTES.labels(bucket=stats.bucket).set(stats.total_bytes)
        STORAGE_TOTAL_OBJECTS.labels(bucket=stats.bucket).set(stats.total_object_count)
    except Exception:
        pass
    return stats


@router.post("/storage/cleanup-preview", response_model=StorageCleanupPreviewOut)
async def storage_cleanup_preview(
    body: StorageCleanupPreviewIn,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_engineer),
):
    def _run(session):
        policies = load_active_policies(session) if body.use_active_policies else []
        if policies:
            return preview_storage_cleanup(session, policies=policies)
        return preview_storage_cleanup(
            session,
            prefixes=body.prefixes,
            retention_days=body.retention_days,
        )

    return await db.run_sync(_run)


@router.post("/storage/cleanup-execute", response_model=StorageCleanupExecuteOut)
async def storage_cleanup_execute(
    body: StorageCleanupExecuteIn,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_admin),
):
    return await db.run_sync(
        lambda session: execute_storage_cleanup(
            session,
            object_names=body.object_names,
            prefixes=body.prefixes,
            repair_orphan_references=body.repair_orphan_references,
        )
    )


@router.get("/storage/policies", response_model=list[StoragePolicyOut])
async def list_storage_policies(
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_admin),
):
    rows = (await db.execute(select(StoragePolicy).order_by(StoragePolicy.id.asc()))).scalars().all()
    return rows


@router.post("/storage/policies", response_model=StoragePolicyOut)
async def create_storage_policy(
    body: StoragePolicyCreateIn,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_admin),
):
    payload = body.model_dump()
    payload["prefix"] = _normalize_prefix(payload["prefix"])
    policy = StoragePolicy(**payload)
    db.add(policy)
    try:
        await db.commit()
    except IntegrityError:
        await db.rollback()
        raise HTTPException(status_code=409, detail="名称或前缀已存在")
    await db.refresh(policy)
    return policy


@router.patch("/storage/policies/{policy_id}", response_model=StoragePolicyOut)
async def update_storage_policy(
    policy_id: int,
    body: StoragePolicyUpdateIn,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_admin),
):
    policy = await db.get(StoragePolicy, policy_id)
    if not policy:
        raise HTTPException(status_code=404, detail="清理策略不存在")
    payload = body.model_dump(exclude_unset=True)
    if "prefix" in payload and payload["prefix"] is not None:
        payload["prefix"] = _normalize_prefix(payload["prefix"])
    for key, value in payload.items():
        setattr(policy, key, value)
    try:
        await db.commit()
    except IntegrityError:
        await db.rollback()
        raise HTTPException(status_code=409, detail="名称或前缀已存在")
    await db.refresh(policy)
    return policy


@router.delete("/storage/policies/{policy_id}")
async def delete_storage_policy(
    policy_id: int,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_admin),
):
    policy = await db.get(StoragePolicy, policy_id)
    if not policy:
        raise HTTPException(status_code=404, detail="清理策略不存在")
    await db.delete(policy)
    await db.commit()
    return {"ok": True}


@router.get("/storage/alert")
async def storage_alert(
    _: User = Depends(get_current_user),
):
    """返回当前存储告警状态，未告警时 alert 为 null。"""
    alert = await get_current_alert()
    return {"alert": alert}


_MEDIA_ALLOWED_PREFIXES = (
    "screenshots/",
    "videos/",
    "traces/",
    "gifs/",
    "reports/",
    "visual-diffs/",
    "visual-baselines/",
    "apks/",
    "ios-apps/",
    "mobile-special/",
    "android-special/",
    "android-artifacts/",
    "ios-artifacts/",
    "web-files/runs/",
    "runs/",
    "performance/",
)

_MEDIA_PROJECT_PATTERNS = (
    re.compile(r"^(?:apks|ios-apps|web-files|visual-baselines)/projects/(\d+)/"),
    re.compile(r"^(?:reports|traces)/recordings/(\d+)/"),
    re.compile(r"^performance/scripts/(\d+)/"),
)
_MEDIA_TEST_RUN_PATTERNS = (
    re.compile(
        r"^(?:screenshots|videos|traces|gifs|android-artifacts|ios-artifacts|visual-diffs|web-files)/runs/(\d+)/"
    ),
    re.compile(r"^reports/run-(\d+)/"),
)
_MEDIA_SPECIAL_RUN_PATTERNS = (
    re.compile(r"^(?:mobile-special|android-special)/runs/(\d+)/"),
    re.compile(r"^runs/(\d+)/incidents/"),
)
_MEDIA_PERF_RUN_RE = re.compile(r"^performance/runs/(\d+)/")
_SAFE_FILENAME_RE = re.compile(r"[^A-Za-z0-9._-]")


async def _ensure_media_access(db: AsyncSession, current_user: User, clean_obj: str) -> None:
    project_id: int | None = None
    for pat in _MEDIA_PROJECT_PATTERNS:
        if m := pat.match(clean_obj):
            project_id = int(m.group(1))
            break
    if project_id is None:
        for pat in _MEDIA_TEST_RUN_PATTERNS:
            if m := pat.match(clean_obj):
                run_id = int(m.group(1))
                stmt = (
                    select(Module.project_id)
                    .join(TestCase, TestCase.module_id == Module.id)
                    .join(TestRun, TestRun.case_id == TestCase.id)
                    .where(TestRun.id == run_id)
                )
                project_id = (await db.execute(stmt)).scalar_one_or_none()
                break
    if project_id is None:
        for pat in _MEDIA_SPECIAL_RUN_PATTERNS:
            if m := pat.match(clean_obj):
                run_id = int(m.group(1))
                stmt = (
                    select(MobileSpecialTask.project_id)
                    .join(MobileSpecialRun, MobileSpecialRun.task_id == MobileSpecialTask.id)
                    .where(MobileSpecialRun.id == run_id)
                )
                project_id = (await db.execute(stmt)).scalar_one_or_none()
                break
    if project_id is None:
        if m := _MEDIA_PERF_RUN_RE.match(clean_obj):
            run_id = int(m.group(1))
            stmt = select(PerformanceRun.project_id).where(PerformanceRun.id == run_id)
            project_id = (await db.execute(stmt)).scalar_one_or_none()

    if project_id is not None:
        await assert_project_access(db, current_user, project_id, ProjectRole.viewer)
    elif getattr(current_user, "role", None) != UserRole.admin:
        raise HTTPException(status_code=403, detail="无权访问该存储对象")


@router.get("/storage/media/{object_name:path}")
async def get_storage_media(
    object_name: str,
    _: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """通过后端安全代理读取 MinIO/Local 中的截图、视频和录制文件。

    彻底解决直接暴露私有 MinIO 端口、局域网访问 127.0.0.1 及 AWS v4 签名头不匹配的问题。
    """
    from app.core.minio_client import read_bytes

    clean_obj = object_name.strip().replace("\\", "/").lstrip("/")
    if not clean_obj or ".." in clean_obj.split("/") or clean_obj.startswith("/"):
        raise HTTPException(status_code=400, detail="非法对象路径")
    if not clean_obj.startswith(_MEDIA_ALLOWED_PREFIXES):
        raise HTTPException(status_code=403, detail="无权访问该存储对象")

    if _ is not None and hasattr(db, "execute"):
        await _ensure_media_access(db, _, clean_obj)

    content_type, _ = mimetypes.guess_type(clean_obj)
    if not content_type:
        if clean_obj.endswith(".webm"):
            content_type = "video/webm"
        elif clean_obj.endswith(".gif"):
            content_type = "image/gif"
        elif clean_obj.endswith(".png"):
            content_type = "image/png"
        elif clean_obj.endswith(".zip"):
            content_type = "application/zip"
        else:
            content_type = "application/octet-stream"

    is_safe_inline = (content_type.startswith("image/") and content_type != "image/svg+xml") or content_type.startswith(
        "video/"
    )
    disposition = "inline" if is_safe_inline else "attachment"
    safe_filename = _SAFE_FILENAME_RE.sub("_", clean_obj.rsplit("/", 1)[-1]) or "file"

    try:
        data = await asyncio.to_thread(read_bytes, clean_obj)
        return Response(
            content=data,
            media_type=content_type,
            headers={
                "Content-Disposition": f'{disposition}; filename="{safe_filename}"',
                "Cache-Control": "private, max-age=3600",
                "X-Content-Type-Options": "nosniff",
            },
        )
    except Exception as exc:
        raise HTTPException(status_code=404, detail="文件不存在或无法读取") from exc
