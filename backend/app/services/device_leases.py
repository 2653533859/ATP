"""Android 设备租约服务。"""

from __future__ import annotations

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
