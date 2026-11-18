import asyncio
import inspect
import json
import os
import time
from typing import Annotated
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.config import settings
from app.models.device import Device, DeviceGroup, DeviceStatus
from app.models.user import User
from app.schemas.device import (
    AndroidWorkerOut,
    DeviceClaimIn,
    DeviceGroupOut,
    DeviceGroupSave,
    DeviceOut,
    DeviceScanItemOut,
    DeviceScanOut,
    DeviceUpdate,
    RemoteDeviceConnectIn,
    RemoteDeviceDisconnectIn,
    RemoteDeviceConnectOut,
    UnifiedDeviceOut,
)
from app.services.ios_device_manager import get_unified_device_list
from app.schemas.device_lease import (
    DeviceLeaseAcquireIn,
    DeviceLeaseForceTakeoverIn,
    DeviceLeaseOut,
    DeviceLeaseTokenIn,
)
from app.api.deps import get_current_user, require_admin, require_engineer
from app.services.adb_service import (
    async_scan_devices,
    async_connect_remote_device,
    async_disconnect_remote_device,
)
from app.services.android_worker_registry import (
    AndroidWorkerRegistryError,
    get_android_worker,
    list_android_workers,
    normalize_worker_id,
    worker_android_queue,
    worker_execution_queue,
)
from app.services.device_resolution import DeviceResolutionError, resolve_device_async
from app.services.audit import write_audit_log
from app.services.device_sync import device_scan_lock, sync_devices_to_db_async
from app.services.device_leases import (
    DeviceLeaseConflict,
    acquire_device_lease,
    force_takeover_device_lease,
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
    worker_id: Annotated[str | None, Query(description="按 Android Worker 节点过滤")] = None,
    unclaimed_only: Annotated[bool, Query(description="仅返回待认领设备")] = False,
    db: AsyncSession = Depends(get_db),
    _=Depends(get_current_user),
):
    q = select(Device).order_by(Device.status.asc(), Device.updated_at.desc())
    if status_filter:
        q = q.where(Device.status == status_filter)
    if unclaimed_only:
        q = q.where(Device.worker_id.is_(None))
    elif worker_id:
        q = q.where(Device.worker_id == worker_id.strip())
    result = await db.execute(q)
    return result.scalars().all()


@router.get("/devices/unified", response_model=list[UnifiedDeviceOut])
async def list_unified_devices(
    platform: str | None = None,
    status: str | None = None,
    db: AsyncSession = Depends(get_db),
    _user: User = Depends(get_current_user),
):
    """获取 Android 与 iOS 统一设备列表，支持跨平台设备资产聚合。"""
    return await get_unified_device_list(db, platform_filter=platform, status_filter=status)


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


_AGGREGATE_SCAN_KEY_PREFIX = "atp:android-scan:"


async def _save_aggregate_scan(parent_scan_id: str, items: list[dict[str, object]]) -> None:
    from app.core.redis_client import close_async_redis, get_async_redis

    redis = get_async_redis()
    try:
        await redis.set(
            f"{_AGGREGATE_SCAN_KEY_PREFIX}{parent_scan_id}",
            json.dumps({"items": items, "created_at": time.time()}, ensure_ascii=False),
            ex=300,
        )
    finally:
        await close_async_redis(redis)


async def _load_aggregate_scan(parent_scan_id: str) -> dict[str, object] | None:
    from app.core.redis_client import close_async_redis, get_async_redis

    redis = get_async_redis()
    try:
        raw = await redis.get(f"{_AGGREGATE_SCAN_KEY_PREFIX}{parent_scan_id}")
        if not raw:
            return None
        if isinstance(raw, bytes):
            raw = raw.decode("utf-8", errors="replace")
        parsed = json.loads(raw)
        return parsed if isinstance(parsed, dict) else None
    except Exception:
        return None
    finally:
        await close_async_redis(redis)


async def _sync_with_optional_worker(db: AsyncSession, scanned: list, worker_id: str) -> None:
    sig = inspect.signature(sync_devices_to_db_async)
    if "worker_id" in sig.parameters:
        await sync_devices_to_db_async(db, scanned, worker_id=worker_id)
    else:
        await sync_devices_to_db_async(db, scanned)


@router.post("/devices/scan", response_model=DeviceScanOut)
async def scan_devices(
    worker_id: Annotated[str | None, Query(description="指定要扫描的 Android Worker 节点 ID")] = None,
    db: AsyncSession = Depends(get_db),
    _=Depends(require_engineer),
):
    """手动触发 ADB 设备扫描，更新数据库并返回最新设备列表"""
    if settings.ADB_SCAN_MODE.strip().lower() == "worker":
        from app.worker.tasks_device import scan_adb_devices

        normalized_worker = worker_id.strip() if worker_id else ""
        if normalized_worker:
            try:
                worker_info = await get_android_worker(normalized_worker)
            except AndroidWorkerRegistryError as exc:
                raise HTTPException(status_code=503, detail=f"worker_registry_unavailable: {exc}") from exc
            if not worker_info:
                raise HTTPException(
                    status_code=503,
                    detail=f"worker_offline: Android Worker '{normalized_worker}' 当前离线",
                )
            queue = worker_android_queue(normalized_worker) if settings.ANDROID_MULTI_NODE_ENABLED else "android"
            task = scan_adb_devices.apply_async(
                kwargs={
                    "worker_id": normalized_worker,
                    "expected_generation": worker_info.get("instance_generation"),
                },
                queue=queue,
                ignore_result=False,
                expires=max(15, int(settings.ADB_SCAN_INTERVAL)),
            )
            return DeviceScanOut(
                status="queued",
                scan_id=str(getattr(task, "id", "") or "") or None,
                total_workers=1,
                devices=await _list_device_rows(db),
            )

        if settings.ANDROID_MULTI_NODE_ENABLED:
            try:
                workers = await list_android_workers()
            except AndroidWorkerRegistryError as exc:
                raise HTTPException(status_code=503, detail=f"worker_registry_unavailable: {exc}") from exc
            if not workers:
                return DeviceScanOut(
                    status="failed",
                    error="no_online_android_worker: 当前没有在线的 Android Worker",
                    devices=await _list_device_rows(db),
                )
            parent_scan_id = f"agg-{uuid4()}"
            items: list[DeviceScanItemOut] = []
            stored_items: list[dict[str, object]] = []
            expires = max(15, int(settings.ADB_SCAN_INTERVAL))
            for item in workers:
                wid = str(item.get("worker_id") or "").strip()
                if not wid:
                    continue
                task = scan_adb_devices.apply_async(
                    kwargs={"worker_id": wid, "expected_generation": item.get("instance_generation")},
                    queue=worker_android_queue(wid),
                    ignore_result=False,
                    expires=expires,
                )
                sub_id = str(getattr(task, "id", "") or uuid4())
                items.append(DeviceScanItemOut(worker_id=wid, scan_id=sub_id, status="queued"))
                stored_items.append({"worker_id": wid, "scan_id": sub_id})
            await _save_aggregate_scan(parent_scan_id, stored_items)
            return DeviceScanOut(
                status="queued",
                scan_id=parent_scan_id,
                total_workers=len(items),
                items=items,
                devices=await _list_device_rows(db),
            )

        task = scan_adb_devices.apply_async(queue="android", ignore_result=False)
        return DeviceScanOut(
            status="queued",
            scan_id=str(getattr(task, "id", "") or "") or None,
            devices=await _list_device_rows(db),
        )

    # 与本地后台巡检共用扫描锁：先开始的扫描不能晚提交、覆盖本次结果。
    local_owner = settings.ANDROID_LOCAL_OWNER_ID.strip() or "local"
    async with device_scan_lock():
        scanned = await async_scan_devices()
        if scanned is None:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="ADB 扫描失败，请检查 ADB 服务后重试",
            )
        await _sync_with_optional_worker(db, scanned, local_owner)
        await db.commit()

    return DeviceScanOut(status="completed", devices=await _list_device_rows(db))


@router.post("/devices/connect", response_model=RemoteDeviceConnectOut)
async def connect_remote_adb_device(
    body: RemoteDeviceConnectIn,
    db: AsyncSession = Depends(get_db),
    _=Depends(require_engineer),
):
    """通过网络 ADB (adb connect) 接入远程物理或云设备。"""
    host = body.host.strip()
    port = body.port
    if ":" in host:
        parts = host.split(":", 1)
        host = parts[0].strip()
        try:
            port = int(parts[1])
        except ValueError:
            pass
    serial = f"{host}:{port}"

    if settings.ADB_SCAN_MODE.strip().lower() == "worker":
        from app.worker.tasks_device import run_android_device_operation, scan_adb_devices

        target_worker = (body.worker_id or "").strip()
        if not target_worker:
            if settings.ANDROID_MULTI_NODE_ENABLED:
                raise HTTPException(status_code=400, detail="多节点模式下远程连接必须明确指定 worker_id")
            try:
                workers = await list_android_workers()
            except AndroidWorkerRegistryError as exc:
                raise HTTPException(status_code=503, detail=f"worker_registry_unavailable: {exc}") from exc
            if len(workers) == 1:
                target_worker = str(workers[0].get("worker_id") or "").strip()
            else:
                raise HTTPException(status_code=400, detail="远程连接必须指定在线的 worker_id")

        try:
            worker_info = await get_android_worker(target_worker)
        except AndroidWorkerRegistryError as exc:
            raise HTTPException(status_code=503, detail=f"worker_registry_unavailable: {exc}") from exc
        if not worker_info:
            raise HTTPException(status_code=503, detail=f"worker_offline: Android Worker '{target_worker}' 当前离线")

        exec_queue = (
            worker_execution_queue(target_worker)
            if settings.ANDROID_MULTI_NODE_ENABLED
            else (settings.ANDROID_WORKER_QUEUE.strip() or "mobile_special")
        )
        scan_queue = worker_android_queue(target_worker) if settings.ANDROID_MULTI_NODE_ENABLED else "android"
        op_task = run_android_device_operation.apply_async(
            args=[
                "connect",
                serial,
                {
                    "host": host,
                    "port": port,
                    "expected_worker_id": target_worker,
                    "expected_generation": worker_info.get("instance_generation"),
                },
            ],
            queue=exec_queue,
            ignore_result=False,
            expires=15,
        )
        try:
            op_result = await asyncio.to_thread(op_task.get, timeout=15)
        except Exception as exc:
            raise HTTPException(
                status_code=504,
                detail="operation_outcome_unknown: 远程设备连接超时，请核实后重试",
            ) from exc
        if not isinstance(op_result, dict) or not op_result.get("ok"):
            raise HTTPException(
                status_code=400,
                detail=f"远程设备连接失败: {(op_result or {}).get('error') or '未知错误'}",
            )

        sync_task = scan_adb_devices.apply_async(
            kwargs={"worker_id": target_worker, "expected_generation": worker_info.get("instance_generation")},
            queue=scan_queue,
            ignore_result=False,
            expires=15,
        )
        try:
            await asyncio.to_thread(sync_task.get, timeout=15)
        except Exception:
            pass
        device = await db.scalar(select(Device).where(Device.worker_id == target_worker, Device.serial == serial))
        return RemoteDeviceConnectOut(
            success=True,
            message=str(op_result.get("message") or f"已连接到 {serial}"),
            serial=serial,
            device=device,
        )

    success, message = await async_connect_remote_device(host, port)
    if not success:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"远程设备连接失败: {message}",
        )

    local_owner = settings.ANDROID_LOCAL_OWNER_ID.strip() or "local"
    async with device_scan_lock():
        scanned = await async_scan_devices()
        if scanned:
            await _sync_with_optional_worker(db, scanned, local_owner)
            await db.commit()

    device = await db.scalar(select(Device).where(Device.worker_id == local_owner, Device.serial == serial))
    if device is None:
        device = await db.scalar(select(Device).where(Device.worker_id.is_(None), Device.serial == serial))
    return RemoteDeviceConnectOut(
        success=True,
        message=message,
        serial=serial,
        device=device,
    )


@router.post("/devices/disconnect")
async def disconnect_remote_adb_device(
    body: RemoteDeviceDisconnectIn,
    db: AsyncSession = Depends(get_db),
    _=Depends(require_engineer),
):
    """通过 adb disconnect 断开远程设备的网络连接。"""
    from datetime import datetime, timezone

    from app.models.device import DeviceLease
    from app.services.device_leases import lease_is_active

    serial = body.serial.strip()
    if settings.ADB_SCAN_MODE.strip().lower() == "worker":
        from app.worker.tasks_device import run_android_device_operation, scan_adb_devices

        requested_worker = (body.worker_id or "").strip()
        device = None
        if body.device_id is not None:
            try:
                device = await resolve_device_async(db, device_id=body.device_id, serial=serial or None)
            except DeviceResolutionError as exc:
                raise HTTPException(status_code=400, detail=f"{exc.code}: {exc.message}") from exc
            serial = device.serial
        elif requested_worker:
            device = await db.scalar(
                select(Device).where(Device.worker_id == requested_worker, Device.serial == serial)
            )
        else:
            try:
                device = await resolve_device_async(db, serial=serial)
            except DeviceResolutionError as exc:
                raise HTTPException(status_code=409, detail=f"{exc.code}: {exc.message}") from exc

        if device is not None:
            db_worker = (device.worker_id or "").strip()
            if db_worker and requested_worker and requested_worker != db_worker:
                raise HTTPException(
                    status_code=409,
                    detail=f"worker_id_mismatch: 设备实际归属节点为 '{db_worker}'，不能覆盖为 '{requested_worker}'",
                )
            target_worker = db_worker or requested_worker
            active_lease = await db.scalar(select(DeviceLease).where(DeviceLease.device_id == device.id))
            if isinstance(active_lease, DeviceLease) and lease_is_active(active_lease, datetime.now(timezone.utc)):
                raise HTTPException(
                    status_code=409,
                    detail=f"设备当前正被 [{active_lease.owner_label}] 占用，请等待任务结束或先释放租约后再断开",
                )
        else:
            target_worker = requested_worker

        if not target_worker:
            raise HTTPException(status_code=400, detail="device_unclaimed: 无法确定设备所属 Android Worker 节点")
        try:
            worker_info = await get_android_worker(target_worker)
        except AndroidWorkerRegistryError as exc:
            raise HTTPException(status_code=503, detail=f"worker_registry_unavailable: {exc}") from exc
        if not worker_info:
            raise HTTPException(status_code=503, detail=f"worker_offline: Android Worker '{target_worker}' 当前离线")

        exec_queue = (
            worker_execution_queue(target_worker)
            if settings.ANDROID_MULTI_NODE_ENABLED
            else (settings.ANDROID_WORKER_QUEUE.strip() or "mobile_special")
        )
        scan_queue = worker_android_queue(target_worker) if settings.ANDROID_MULTI_NODE_ENABLED else "android"
        op_task = run_android_device_operation.apply_async(
            args=[
                "disconnect",
                serial,
                {
                    "expected_worker_id": target_worker,
                    "expected_generation": worker_info.get("instance_generation"),
                },
            ],
            queue=exec_queue,
            ignore_result=False,
            expires=15,
        )
        try:
            op_result = await asyncio.to_thread(op_task.get, timeout=15)
        except Exception as exc:
            raise HTTPException(
                status_code=504,
                detail="operation_outcome_unknown: 断开设备超时，请核实后重试",
            ) from exc

        sync_task = scan_adb_devices.apply_async(
            kwargs={"worker_id": target_worker, "expected_generation": worker_info.get("instance_generation")},
            queue=scan_queue,
            ignore_result=False,
            expires=15,
        )
        try:
            await asyncio.to_thread(sync_task.get, timeout=15)
        except Exception:
            if device is not None:
                from app.services.device_leases import handle_device_disconnection_recovery

                await handle_device_disconnection_recovery(db, device.id, reason="manual_disconnect")
                await db.commit()
        return {
            "success": bool((op_result or {}).get("ok")),
            "message": str((op_result or {}).get("message") or (op_result or {}).get("error") or ""),
            "serial": serial,
            "worker_id": target_worker,
        }

    local_owner = settings.ANDROID_LOCAL_OWNER_ID.strip() or "local"
    local_device = None
    if hasattr(db, "scalar"):
        local_device = await db.scalar(
            select(Device).where(
                Device.serial == serial,
                (Device.worker_id == local_owner) | Device.worker_id.is_(None),
            )
        )
        if local_device is not None and getattr(local_device, "id", None) is not None:
            active_lease = await db.scalar(select(DeviceLease).where(DeviceLease.device_id == local_device.id))
            if isinstance(active_lease, DeviceLease) and lease_is_active(active_lease, datetime.now(timezone.utc)):
                raise HTTPException(
                    status_code=409,
                    detail=f"设备当前正被 [{active_lease.owner_label}] 占用，请等待任务结束或先释放租约后再断开",
                )

    success, message = await async_disconnect_remote_device(serial)
    async with device_scan_lock():
        scanned = await async_scan_devices()
        if scanned is not None:
            await _sync_with_optional_worker(db, scanned, local_owner)
            await db.commit()
        elif local_device is not None:
            from app.services.device_leases import handle_device_disconnection_recovery

            await handle_device_disconnection_recovery(db, local_device.id, reason="manual_disconnect")
            await db.commit()
    return {"success": success, "message": message, "serial": serial}


@router.post("/devices/{device_id}/disconnection-recovery")
async def trigger_device_disconnection_recovery(
    device_id: int,
    db: AsyncSession = Depends(get_db),
    _=Depends(require_engineer),
):
    """手动或掉线事件触发设备租约清理与在途任务收敛。"""
    from app.services.device_leases import handle_device_disconnection_recovery

    recovery = await handle_device_disconnection_recovery(db, device_id, reason="disconnection_trigger")
    await db.commit()
    return recovery


@router.get("/devices/scan/{scan_id}", response_model=DeviceScanOut)
async def get_scan_status(
    scan_id: str,
    db: AsyncSession = Depends(get_db),
    _=Depends(require_engineer),
):
    """查询 Windows Android Worker 的单节点或全节点聚合 ADB 扫描结果。"""
    from uuid import UUID

    is_aggregate_id = scan_id.startswith("agg-")
    uuid_part = scan_id.removeprefix("agg-")
    try:
        UUID(uuid_part)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail="扫描任务不存在") from exc

    aggregate = await _load_aggregate_scan(scan_id)
    if aggregate is None and is_aggregate_id:
        raise HTTPException(status_code=404, detail="scan_expired: 聚合扫描结果不存在或已过期")
    if aggregate is not None:
        raw_items = aggregate.get("items") if isinstance(aggregate.get("items"), list) else []
        created_at = float(aggregate.get("created_at") or 0.0)
        timed_out_window = created_at > 0 and (time.time() - created_at) > max(30, int(settings.ADB_SCAN_INTERVAL) + 15)
        items: list[DeviceScanItemOut] = []
        completed_count = 0
        failed_count = 0
        running_count = 0

        for entry in raw_items:
            if not isinstance(entry, dict):
                continue
            wid = str(entry.get("worker_id") or "")
            sub_id = str(entry.get("scan_id") or "")
            state, payload = await asyncio.to_thread(_read_scan_result, sub_id)
            if state in {"PENDING", "RECEIVED", "STARTED", "RETRY"}:
                if timed_out_window:
                    failed_count += 1
                    items.append(DeviceScanItemOut(worker_id=wid, scan_id=sub_id, status="timed_out", error="扫描超时"))
                else:
                    running_count += 1
                    items.append(
                        DeviceScanItemOut(
                            worker_id=wid,
                            scan_id=sub_id,
                            status="running" if state in {"STARTED", "RETRY"} else "queued",
                        )
                    )
            elif state == "SUCCESS" and isinstance(payload, dict) and payload.get("status") == "completed":
                completed_count += 1
                items.append(
                    DeviceScanItemOut(
                        worker_id=wid,
                        scan_id=sub_id,
                        status="completed",
                        count=int(payload.get("count") or 0),
                    )
                )
            else:
                failed_count += 1
                err = payload.get("error") if isinstance(payload, dict) else "ADB 扫描任务执行失败"
                items.append(
                    DeviceScanItemOut(worker_id=wid, scan_id=sub_id, status="failed", error=str(err or "失败"))
                )

        total = len(items)
        if running_count > 0:
            agg_status = "running"
        elif completed_count == total and total > 0:
            agg_status = "completed"
        elif completed_count > 0 and failed_count > 0:
            agg_status = "partial_failed"
        else:
            agg_status = "failed"

        return DeviceScanOut(
            status=agg_status,
            scan_id=scan_id,
            total_workers=total,
            completed_workers=completed_count,
            failed_workers=failed_count,
            items=items,
            devices=await _list_device_rows(db),
        )

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


@router.post("/devices/{device_id}/claim", response_model=DeviceOut)
async def claim_device_worker(
    device_id: int,
    body: DeviceClaimIn,
    request: Request = None,  # type: ignore[assignment]
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    """将历史未认领设备归属到指定在线 Android Worker 节点（仅管理员，写入审计日志）。"""
    from datetime import datetime, timezone

    from app.models.device import DeviceLease
    from app.services.device_leases import lease_is_active

    device = await db.get(Device, device_id)
    if not device:
        raise HTTPException(status_code=404, detail="设备不存在")
    try:
        target_worker = normalize_worker_id(body.worker_id)
    except AndroidWorkerRegistryError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    previous_worker = (device.worker_id or "").strip() or None
    if previous_worker and previous_worker != target_worker and not body.force:
        raise HTTPException(
            status_code=409,
            detail=f"设备已归属到节点 '{previous_worker}'，如需改绑请确认设备空闲并显式传入 force=true",
        )

    active_lease = await db.scalar(select(DeviceLease).where(DeviceLease.device_id == device.id))
    if active_lease is not None and lease_is_active(active_lease, datetime.now(timezone.utc)):
        raise HTTPException(
            status_code=409,
            detail=f"设备当前正被 [{active_lease.owner_label}] 占用，不能在运行或控制期间变更节点归属",
        )

    worker_hostname = body.worker_hostname.strip() if body.worker_hostname else None
    if settings.ANDROID_MULTI_NODE_ENABLED and not settings.ATP_LOCAL_MODE:
        try:
            worker_info = await get_android_worker(target_worker)
        except AndroidWorkerRegistryError as exc:
            raise HTTPException(status_code=503, detail=f"worker_registry_unavailable: {exc}") from exc
        if not worker_info:
            raise HTTPException(status_code=503, detail=f"worker_offline: 目标节点 '{target_worker}' 当前不在线")
        if not worker_hostname and worker_info.get("hostname"):
            worker_hostname = str(worker_info["hostname"])

    conflict = await db.scalar(
        select(Device).where(Device.worker_id == target_worker, Device.serial == device.serial, Device.id != device.id)
    )
    if conflict is not None:
        raise HTTPException(
            status_code=409,
            detail=f"节点 {target_worker} 下已存在序列号 {device.serial} 的设备记录 (id={conflict.id})",
        )
    device.worker_id = target_worker
    if worker_hostname is not None:
        device.worker_hostname = worker_hostname
    await write_audit_log(
        db,
        action="device.claim_worker",
        resource_type="device",
        resource_id=device.id,
        user_id=current_user.id,
        username=current_user.username,
        ip_address=request.client.host if request is not None and request.client is not None else "",
        detail=f"serial={device.serial}; from={previous_worker or 'unclaimed'}; to={target_worker}",
    )
    await db.commit()
    await db.refresh(device)
    return device


@router.get("/devices/workers", response_model=list[AndroidWorkerOut])
async def list_android_worker_status(
    _=Depends(require_engineer),
):
    """返回当前通过 Redis 心跳注册的 Windows Android Worker，或直连 ADB 状态。"""
    if settings.ATP_LOCAL_MODE:
        return []
    if settings.ADB_SERVER_SOCKET.strip():
        target = settings.ADB_SERVER_SOCKET.strip()
        now = time.time()
        return [
            {
                "worker_id": f"Direct-ADB ({target})",
                "status": "online",
                "queues": ["direct"],
                "capabilities": ["adb-direct"],
                "hostname": target,
                "pid": os.getpid(),
                "updated_at": now,
                "expires_at": now + 3600.0,
            }
        ]
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
            takeover_own=body.takeover_own,
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
        lease = await heartbeat_device_lease(db, device_id, body.lease_token, ttl_seconds=body.ttl_seconds)
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


@router.post("/devices/{device_id}/lease/force-takeover", response_model=DeviceLeaseOut)
async def force_takeover_lease(
    device_id: int,
    body: DeviceLeaseForceTakeoverIn,
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    """管理员在原租约释放后获取设备控制权并写入审计日志。"""
    try:
        lease = await force_takeover_device_lease(
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

    detail_parts = [f"owner_label={body.owner_label}"]
    reason = body.reason.strip()
    if reason:
        detail_parts.append(f"reason={reason}")
    await write_audit_log(
        db,
        action="device_lease_force_takeover",
        resource_type="device",
        resource_id=device_id,
        user_id=current_user.id,
        username=current_user.username,
        detail="; ".join(detail_parts),
        ip_address=request.client.host if request.client else "",
        raise_on_error=True,
    )
    await db.commit()
    await db.refresh(lease)
    return DeviceLeaseOut.model_validate(lease)
