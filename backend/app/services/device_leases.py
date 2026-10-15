"""Android 设备租约服务。"""

from __future__ import annotations

from typing import Any
import secrets
from datetime import datetime, timedelta, timezone

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.device import Device, DeviceLease, DeviceStatus


class DeviceLeaseConflict(RuntimeError):
    pass


def _now() -> datetime:
    return datetime.now(timezone.utc)


async def acquire_device_lease(
    db: AsyncSession,
    device_id: int,
    *,
    owner_id: int | None,
    owner_label: str,
    ttl_seconds: int = 900,
) -> DeviceLease:
    now = _now()
    device = (await db.execute(select(Device).where(Device.id == device_id).with_for_update())).scalar_one_or_none()
    if device is None:
        raise LookupError("设备不存在")
    if device.status == DeviceStatus.offline:
        raise DeviceLeaseConflict("设备当前离线，无法占用")

    current = (await db.execute(select(DeviceLease).where(DeviceLease.device_id == device_id))).scalar_one_or_none()
    if current is not None:
        if current.expires_at > now:
            raise DeviceLeaseConflict("设备已被其他任务占用")
        await db.delete(current)
        await db.flush()

    lease = DeviceLease(
        device_id=device_id,
        lease_token=secrets.token_urlsafe(48),
        owner_id=owner_id,
        owner_label=owner_label,
        acquired_at=now,
        heartbeat_at=now,
        expires_at=now + timedelta(seconds=ttl_seconds),
    )
    db.add(lease)
    device.status = DeviceStatus.busy
    await db.flush()
    return lease


async def heartbeat_device_lease(
    db: AsyncSession,
    device_id: int,
    lease_token: str,
    *,
    ttl_seconds: int = 900,
) -> DeviceLease:
    lease = (
        await db.execute(
            select(DeviceLease).where(DeviceLease.device_id == device_id, DeviceLease.lease_token == lease_token)
        )
    ).scalar_one_or_none()
    if lease is None or lease.expires_at <= _now():
        raise DeviceLeaseConflict("设备租约不存在或已过期")
    now = _now()
    lease.heartbeat_at = now
    lease.expires_at = now + timedelta(seconds=ttl_seconds)
    await db.flush()
    return lease


async def get_active_device_lease(
    db: AsyncSession,
    device_id: int,
    lease_token: str,
) -> DeviceLease | None:
    """返回指定设备的有效租约；控制面调用必须使用该令牌。"""
    lease = (
        await db.execute(
            select(DeviceLease).where(DeviceLease.device_id == device_id, DeviceLease.lease_token == lease_token)
        )
    ).scalar_one_or_none()
    if lease is None or lease.expires_at <= _now():
        return None
    return lease


async def release_device_lease(db: AsyncSession, device_id: int, lease_token: str) -> bool:
    lease = (
        await db.execute(
            select(DeviceLease).where(DeviceLease.device_id == device_id, DeviceLease.lease_token == lease_token)
        )
    ).scalar_one_or_none()
    if lease is None:
        return False
    device = await db.get(Device, device_id)
    await db.delete(lease)
    if device is not None and device.status != DeviceStatus.offline:
        device.status = DeviceStatus.online
    await db.flush()
    return True


async def reclaim_expired_device_leases(db: AsyncSession) -> int:
    now = _now()
    expired = (await db.execute(select(DeviceLease).where(DeviceLease.expires_at <= now))).scalars().all()
    count = 0
    for lease in expired:
        device = await db.get(Device, lease.device_id)
        await db.delete(lease)
        if device is not None and device.status == DeviceStatus.busy:
            device.status = DeviceStatus.online
        count += 1
    await db.flush()
    return count


async def acquire_available_device_from_pool(
    db: AsyncSession,
    device_ids: list[int] | None = None,
    *,
    owner_id: int | None,
    owner_label: str,
    ttl_seconds: int = 900,
) -> tuple[Device, DeviceLease] | None:
    """从设备池中寻找第一个可用的在线设备并锁定获取租约。"""
    query = select(Device).where(Device.status != DeviceStatus.offline)
    if device_ids:
        query = query.where(Device.id.in_(device_ids))

    devices = (await db.execute(query)).scalars().all()
    for dev in devices:
        try:
            lease = await acquire_device_lease(
                db,
                dev.id,
                owner_id=owner_id,
                owner_label=owner_label,
                ttl_seconds=ttl_seconds,
            )
            return dev, lease
        except DeviceLeaseConflict:
            continue
    return None


async def handle_device_disconnection_recovery(
    db: AsyncSession, device_id: int, reason: str = "设备异常断开"
) -> dict[str, Any]:
    """当设备掉线或失联时：强制标记 offline、清除活动租约、收敛在途执行记录。"""
    now = _now()
    device = await db.get(Device, device_id)
    if device is not None:
        device.status = DeviceStatus.offline
        device.last_seen_at = now

    # 1. 清理活动租约
    leases_res = await db.execute(select(DeviceLease).where(DeviceLease.device_id == device_id))
    leases = leases_res.scalars().all()
    for lease in leases:
        await db.delete(lease)

    # 2. 收敛在途 TestRun
    recovered_runs_count = 0
    if device is not None:
        from app.models.case import RunStatus, TestRun

        runs_res = await db.execute(
            select(TestRun).where(
                TestRun.status.in_([RunStatus.pending, RunStatus.running]),
            )
        )
        runs = runs_res.scalars().all()
        for run in runs:
            summary = run.result_summary or {}
            if summary.get("device_serial") == device.serial or summary.get("device_id") == device.id:
                run.status = RunStatus.error
                run.error_message = f"执行设备异常掉线或失联: {reason}"
                recovered_runs_count += 1

    await db.flush()
    return {
        "device_id": device_id,
        "released_leases": len(leases),
        "recovered_runs": recovered_runs_count,
    }


def expand_case_items_for_device_matrix(
    case_items: list[dict[str, Any]],
    android_case_ids: set[int],
    device_ids: list[Any],
) -> list[dict[str, Any]]:
    """将套件中 Android 用例按真机矩阵设备列表展开。"""
    if not device_ids or not android_case_ids:
        return list(case_items)

    expanded: list[dict[str, Any]] = []
    for item in case_items:
        cid = item.get("case_id")
        if cid in android_case_ids:
            for dev_item in device_ids:
                dev_id = dev_item if isinstance(dev_item, int) else dev_item.get("device_id")
                if dev_id:
                    expanded.append(
                        {
                            **item,
                            "device_id": dev_id,
                            "extra_vars": {**(item.get("extra_vars") or {}), "device_id": dev_id},
                        }
                    )
        else:
            expanded.append(item)
    return expanded
