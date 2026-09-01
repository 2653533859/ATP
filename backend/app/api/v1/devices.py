import asyncio

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.config import settings
from app.models.device import Device, DeviceGroup, DeviceStatus
from app.models.user import User
from app.schemas.device import AndroidWorkerOut, DeviceGroupOut, DeviceGroupSave, DeviceOut, DeviceScanOut, DeviceUpdate
from app.schemas.device_lease import DeviceLeaseAcquireIn, DeviceLeaseOut, DeviceLeaseTokenIn
from app.api.deps import get_current_user, require_engineer
from app.services.adb_service import async_scan_devices
from app.services.android_worker_registry import AndroidWorkerRegistryError, list_android_workers
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


async def _resolve_group_devices(db: AsyncSession, device_ids: list[int]) -> list[Device]:
    unique_ids = list(dict.fromkeys(device_ids))
    if not unique_ids:
        return []
    result = await db.execute(select(Device).where(Device.id.in_(unique_ids)))
    devices = list(result.scalars().all())
    if len(devices) != len(unique_ids):
        raise HTTPException(status_code=422, detail="设备组包含不存在的设备")
    return devices


@router.get("/device-groups", response_model=list[DeviceGroupOut])
async def list_device_groups(db: AsyncSession = Depends(get_db), _=Depends(get_current_user)):
    result = await db.execute(select(DeviceGroup).order_by(DeviceGroup.name.asc()))
    return result.scalars().unique().all()


@router.post("/device-groups", response_model=DeviceGroupOut, status_code=status.HTTP_201_CREATED)
async def create_device_group(
    body: DeviceGroupSave,
    db: AsyncSession = Depends(get_db),
    _=Depends(require_engineer),
):
    if await db.scalar(select(DeviceGroup.id).where(DeviceGroup.name == body.name.strip())):
        raise HTTPException(status_code=409, detail="设备组名称已存在")
    group = DeviceGroup(
        name=body.name.strip(),
        description=body.description,
        devices=await _resolve_group_devices(db, body.device_ids),
    )
    db.add(group)
    await db.commit()
    await db.refresh(group)
    return group


@router.put("/device-groups/{group_id}", response_model=DeviceGroupOut)
async def update_device_group(
    group_id: int,
    body: DeviceGroupSave,
    db: AsyncSession = Depends(get_db),
    _=Depends(require_engineer),
):
    group = await db.get(DeviceGroup, group_id)
    if not group:
        raise HTTPException(status_code=404, detail="设备组不存在")
    duplicate = await db.scalar(
        select(DeviceGroup.id).where(DeviceGroup.name == body.name.strip(), DeviceGroup.id != group_id)
    )
    if duplicate:
        raise HTTPException(status_code=409, detail="设备组名称已存在")
    group.name = body.name.strip()
    group.description = body.description
    group.devices = await _resolve_group_devices(db, body.device_ids)
    await db.commit()
    await db.refresh(group)
    return group


@router.delete("/device-groups/{group_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_device_group(group_id: int, db: AsyncSession = Depends(get_db), _=Depends(require_engineer)):
    group = await db.get(DeviceGroup, group_id)
    if not group:
        raise HTTPException(status_code=404, detail="设备组不存在")
    await db.delete(group)
    await db.commit()


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


async def _list_device_rows(db: AsyncSession) -> list[Device]:
    result = await db.execute(select(Device).order_by(Device.status.asc(), Device.updated_at.desc()))
    return list(result.scalars().all())


def _scan_result(scan_id: str):
    from celery.result import AsyncResult

    from app.worker.celery_app import celery_app

    return AsyncResult(scan_id, app=celery_app)


def _read_scan_result(scan_id: str) -> tuple[str, object]:
    task = _scan_result(scan_id)
    state = str(task.state or "PENDING").upper()
    payload = task.result if state == "SUCCESS" else None
    return state, payload


@router.post("/devices/scan", response_model=DeviceScanOut)
async def scan_devices(
    db: AsyncSession = Depends(get_db),
    _=Depends(require_engineer),
):
    """手动触发 ADB 设备扫描，更新数据库并返回最新设备列表"""
    if settings.ADB_SCAN_MODE.strip().lower() == "worker":
        from app.worker.tasks_device import scan_adb_devices

        task = scan_adb_devices.apply_async(queue="mobile_special", ignore_result=False)
        return DeviceScanOut(
            status="queued",
            scan_id=str(getattr(task, "id", "") or "") or None,
            devices=await _list_device_rows(db),
        )

    scanned = await async_scan_devices()
    if scanned is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="ADB 扫描失败，请检查 ADB 服务后重试",
        )
    await sync_devices_to_db_async(db, scanned)
    await db.commit()

    return DeviceScanOut(status="completed", devices=await _list_device_rows(db))


@router.get("/devices/scan/{scan_id}", response_model=DeviceScanOut)
async def get_scan_status(
    scan_id: str,
    db: AsyncSession = Depends(get_db),
    _=Depends(require_engineer),
):
    """查询 Windows Android Worker 的 ADB 扫描结果。"""
    from uuid import UUID

    try:
        UUID(scan_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail="扫描任务不存在") from exc

    try:
        state, payload = await asyncio.to_thread(_read_scan_result, scan_id)
        devices = await _list_device_rows(db)
        if state in {"PENDING", "RECEIVED", "STARTED", "RETRY"}:
            status_value = "running" if state in {"STARTED", "RETRY"} else "queued"
            return DeviceScanOut(status=status_value, scan_id=scan_id, devices=devices)
        if state != "SUCCESS":
            return DeviceScanOut(status="failed", scan_id=scan_id, devices=devices, error="ADB 扫描任务执行失败")
        payload = payload if isinstance(payload, dict) else {}
        if payload.get("status") != "completed":
            return DeviceScanOut(
                status="failed",
                scan_id=scan_id,
                devices=devices,
                error=str(payload.get("error") or "ADB 扫描失败"),
            )
        return DeviceScanOut(status="completed", scan_id=scan_id, devices=devices)
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=503, detail="暂时无法查询 Android Worker 扫描状态") from exc


@router.get("/devices/workers", response_model=list[AndroidWorkerOut])
async def list_android_worker_status(
    _=Depends(require_engineer),
):
    """返回当前通过 Redis 心跳注册的 Windows Android Worker。"""
    try:
        return await list_android_workers()
    except AndroidWorkerRegistryError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc


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
