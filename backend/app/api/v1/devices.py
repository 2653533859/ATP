from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.models.device import Device, DeviceStatus
from app.models.user import User
from app.schemas.device import DeviceOut, DeviceUpdate
from app.schemas.device_lease import DeviceLeaseAcquireIn, DeviceLeaseOut, DeviceLeaseTokenIn
from app.api.deps import get_current_user, require_engineer
from app.services.adb_service import async_scan_devices
from app.services.device_sync import sync_devices_to_db_async
from app.services.device_leases import (
    DeviceLeaseConflict,
    acquire_device_lease,
    heartbeat_device_lease,
    release_device_lease,
)

router = APIRouter(tags=["设备管理"])


def _lease_error(exc: DeviceLeaseConflict) -> HTTPException:
    return HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc))


@router.get("/devices", response_model=list[DeviceOut])
async def list_devices(
    status_filter: DeviceStatus | None = None,
    db: AsyncSession = Depends(get_db),
    _=Depends(get_current_user),
):
    q = select(Device).order_by(Device.status.asc(), Device.updated_at.desc())
    if status_filter:
        q = q.where(Device.status == status_filter)
    result = await db.execute(q)
    return result.scalars().all()


@router.post("/devices/scan", response_model=list[DeviceOut])
async def scan_devices(
    db: AsyncSession = Depends(get_db),
    _=Depends(require_engineer),
):
    """手动触发 ADB 设备扫描，更新数据库并返回最新设备列表"""
    scanned = await async_scan_devices()
    if scanned is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="ADB 扫描失败，请检查 ADB 服务后重试",
        )
    await sync_devices_to_db_async(db, scanned)
    await db.commit()

    # 返回最新设备列表
    result = await db.execute(select(Device).order_by(Device.status.asc(), Device.updated_at.desc()))
    return result.scalars().all()


@router.get("/devices/{device_id}", response_model=DeviceOut)
async def get_device(
    device_id: int,
    db: AsyncSession = Depends(get_db),
    _=Depends(get_current_user),
):
    device = await db.get(Device, device_id)
    if not device:
        raise HTTPException(status_code=404, detail="设备不存在")
    return device


@router.patch("/devices/{device_id}", response_model=DeviceOut)
async def update_device(
    device_id: int,
    body: DeviceUpdate,
    db: AsyncSession = Depends(get_db),
    _=Depends(require_engineer),
):
    device = await db.get(Device, device_id)
    if not device:
        raise HTTPException(status_code=404, detail="设备不存在")
    for k, v in body.model_dump(exclude_none=True).items():
        setattr(device, k, v)
    await db.commit()
    await db.refresh(device)
    return device


@router.delete("/devices/{device_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_device(
    device_id: int,
    db: AsyncSession = Depends(get_db),
    _=Depends(require_engineer),
):
    device = await db.get(Device, device_id)
    if not device:
        raise HTTPException(status_code=404, detail="设备不存在")
    await db.delete(device)
    await db.commit()


@router.post("/devices/{device_id}/lease", response_model=DeviceLeaseOut)
async def acquire_lease(
    device_id: int,
    body: DeviceLeaseAcquireIn,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_engineer),
):
    try:
        lease = await acquire_device_lease(
            db,
            device_id,
            owner_id=current_user.id,
            owner_label=body.owner_label,
            ttl_seconds=body.ttl_seconds,
        )
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except DeviceLeaseConflict as exc:
        raise _lease_error(exc) from exc
    await db.commit()
    await db.refresh(lease)
    return lease


@router.post("/devices/{device_id}/lease/heartbeat", response_model=DeviceLeaseOut)
async def heartbeat_lease(
    device_id: int,
    body: DeviceLeaseTokenIn,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_engineer),
):
    try:
        lease = await heartbeat_device_lease(db, device_id, body.lease_token)
    except DeviceLeaseConflict as exc:
        raise _lease_error(exc) from exc
    await db.commit()
    await db.refresh(lease)
    response = DeviceLeaseOut.model_validate(lease)
    response.lease_token = None
    return response


@router.delete("/devices/{device_id}/lease", status_code=status.HTTP_204_NO_CONTENT)
async def release_lease(
    device_id: int,
    body: DeviceLeaseTokenIn,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_engineer),
):
    released = await release_device_lease(db, device_id, body.lease_token)
    if not released:
        raise HTTPException(status_code=404, detail="设备租约不存在")
    await db.commit()
