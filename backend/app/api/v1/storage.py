from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, require_admin, require_engineer
from app.core.database import get_db
from app.models.storage_policy import StoragePolicy
from app.models.user import User
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
    return await db.run_sync(lambda session: get_storage_stats(session))


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
