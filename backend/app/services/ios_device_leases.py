"""iOS Appium device lease service."""

from __future__ import annotations

import secrets
from datetime import datetime, timedelta, timezone
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.ios import IosDevice, IosDeviceLease, IosDeviceStatus


class IosDeviceLeaseConflict(RuntimeError):
    pass


def _now() -> datetime:
    return datetime.now(timezone.utc)


async def acquire_ios_device_lease(
    db: Any,
    device_id: int,
    *,
    owner_id: int | None,
    owner_label: str,
    ttl_seconds: int = 900,
) -> IosDeviceLease:
    now = _now()
    device = (
        await db.execute(select(IosDevice).where(IosDevice.id == device_id).with_for_update())
    ).scalar_one_or_none()
    if device is None:
        raise LookupError("iOS 设备不存在")
    if device.status == IosDeviceStatus.offline:
        raise IosDeviceLeaseConflict("iOS 设备当前离线，无法占用")
    current = (
        await db.execute(select(IosDeviceLease).where(IosDeviceLease.device_id == device_id))
    ).scalar_one_or_none()
    if current is not None:
        if current.expires_at > now:
            raise IosDeviceLeaseConflict("iOS 设备已被其他任务占用")
        await db.delete(current)
        await db.flush()
    lease = IosDeviceLease(
        device_id=device_id,
        lease_token=secrets.token_urlsafe(48),
        owner_id=owner_id,
        owner_label=owner_label,
        acquired_at=now,
        heartbeat_at=now,
        expires_at=now + timedelta(seconds=ttl_seconds),
    )
    db.add(lease)
    device.status = IosDeviceStatus.busy
    await db.flush()
    return lease


async def heartbeat_ios_device_lease(
    db: Any,
    device_id: int,
    lease_token: str,
    *,
    ttl_seconds: int = 900,
) -> IosDeviceLease:
    lease = (
        await db.execute(
            select(IosDeviceLease).where(
                IosDeviceLease.device_id == device_id, IosDeviceLease.lease_token == lease_token
            )
        )
    ).scalar_one_or_none()
    if lease is None or lease.expires_at <= _now():
        raise IosDeviceLeaseConflict("iOS 设备租约不存在或已过期")
    now = _now()
    lease.heartbeat_at = now
    lease.expires_at = now + timedelta(seconds=ttl_seconds)
    await db.flush()
    return lease


async def release_ios_device_lease(db: Any, device_id: int, lease_token: str) -> bool:
    lease = (
        await db.execute(
            select(IosDeviceLease).where(
                IosDeviceLease.device_id == device_id, IosDeviceLease.lease_token == lease_token
            )
        )
    ).scalar_one_or_none()
    if lease is None:
        return False
    device = await db.get(IosDevice, device_id)
    await db.delete(lease)
    if device is not None and device.status != IosDeviceStatus.offline:
        device.status = IosDeviceStatus.online
    await db.flush()
    return True


async def reclaim_expired_ios_device_leases(db: Any) -> int:
    now = _now()
    expired = (await db.execute(select(IosDeviceLease).where(IosDeviceLease.expires_at <= now))).scalars().all()
    count = 0
    for lease in expired:
        device = await db.get(IosDevice, lease.device_id)
        await db.delete(lease)
        if device is not None and device.status == IosDeviceStatus.busy:
            device.status = IosDeviceStatus.online
        count += 1
    await db.flush()
    return count


async def acquire_available_ios_device_from_pool(
    db: Any,
    candidate_device_ids: list[int],
    *,
    owner_id: int | None = None,
    owner_label: str = "ios_suite_runner",
    ttl_seconds: int = 900,
) -> tuple[IosDevice, IosDeviceLease]:
    """Attempt to acquire a lease on the first available iOS device from a candidate list.

    Iterates through candidate_device_ids and skips busy/offline/leased devices cleanly.
    Raises IosDeviceLeaseConflict only when no candidate devices can be acquired.
    """
    if not candidate_device_ids:
        raise IosDeviceLeaseConflict("未指定任何候选 iOS 设备")

    now = _now()
    for dev_id in candidate_device_ids:
        device = (
            await db.execute(select(IosDevice).where(IosDevice.id == dev_id).with_for_update())
        ).scalar_one_or_none()
        if device is None or device.status == IosDeviceStatus.offline:
            continue

        current = (
            await db.execute(select(IosDeviceLease).where(IosDeviceLease.device_id == dev_id))
        ).scalar_one_or_none()
        if current is not None:
            if current.expires_at > now:
                continue  # Device busy, try next candidate
            await db.delete(current)
            await db.flush()

        lease = IosDeviceLease(
            device_id=dev_id,
            lease_token=secrets.token_urlsafe(48),
            owner_id=owner_id,
            owner_label=owner_label,
            acquired_at=now,
            heartbeat_at=now,
            expires_at=now + timedelta(seconds=ttl_seconds),
        )
        db.add(lease)
        device.status = IosDeviceStatus.busy
        await db.flush()
        return device, lease

    raise IosDeviceLeaseConflict("所有候选 iOS 设备均处于忙碌、占用或离线状态")


async def handle_ios_device_disconnection_recovery(
    db: Any,
    device_id: int,
    reason: str = "iOS 设备异常掉线或断开连接",
) -> dict[str, Any]:
    """Recover from an iOS device disconnection by releasing leases and converging in-flight runs."""
    now = _now()
    device = await db.get(IosDevice, device_id)
    if device is not None:
        device.status = IosDeviceStatus.offline

    # Release any active lease
    active_lease = (
        await db.execute(select(IosDeviceLease).where(IosDeviceLease.device_id == device_id))
    ).scalar_one_or_none()
    released_leases = 0
    if active_lease is not None:
        await db.delete(active_lease)
        released_leases += 1

    # Safely converge in-flight TestRuns if any
    recovered_runs = 0
    from app.models.case import RunStatus, TestRun

    query_runs = select(TestRun).where(
        TestRun.status.in_([RunStatus.running.value, RunStatus.pending.value]),
    )
    res_runs = await db.execute(query_runs)
    in_flight_runs = res_runs.scalars().all()
    for run in in_flight_runs:
        summary_text = str(run.result_summary or "")
        if f'"device_id": {device_id}' in summary_text or f"device_id={device_id}" in summary_text:
            run.status = RunStatus.failed.value
            run.error_message = reason
            run.completed_at = now
            recovered_runs += 1

    await db.flush()
    return {
        "device_id": device_id,
        "released_leases": released_leases,
        "recovered_runs": recovered_runs,
        "status": "offline",
    }
