"""Android 设备租约服务。"""

from __future__ import annotations

from typing import Any
import secrets
from datetime import datetime, timedelta, timezone

from sqlalchemy import delete, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Session
from sqlalchemy.orm.attributes import set_committed_value

from app.models.device import Device, DeviceLease, DeviceStatus


class DeviceLeaseConflict(RuntimeError):
    pass


def _now() -> datetime:
    return datetime.now(timezone.utc)


def lease_is_active(lease: DeviceLease, now: datetime | None = None) -> bool:
    """SQLite 读回的是无时区时间（实际为 UTC），比较前统一，否则会抛 TypeError。"""
    expires_at = lease.expires_at
    if expires_at.tzinfo is None:
        expires_at = expires_at.replace(tzinfo=timezone.utc)
    return expires_at > (now or _now())


async def _device_has_lease(db: AsyncSession, device_id: int) -> bool:
    found = await db.execute(select(DeviceLease.id).where(DeviceLease.device_id == device_id))
    return found.scalar_one_or_none() is not None


def _remaining_text(lease: DeviceLease, now: datetime) -> str:
    expires_at = lease.expires_at
    if expires_at.tzinfo is None:
        expires_at = expires_at.replace(tzinfo=timezone.utc)
    seconds = max(0, int((expires_at - now).total_seconds()))
    if seconds >= 60:
        return f"{seconds // 60} 分 {seconds % 60} 秒"
    return f"{seconds} 秒"


def _conflict_message(lease: DeviceLease | None, now: datetime) -> str:
    """冲突提示带上占用者标签与剩余时长，供投屏弹窗直接展示给用户。"""
    label = (getattr(lease, "owner_label", "") or "").strip()
    if lease is None or not label:
        return "设备已被其他任务占用"
    return f"设备已被“{label}”占用，预计 {_remaining_text(lease, now)} 后释放"


async def _delete_expired_lease(db: AsyncSession, lease_id: int, lease_token: str, now: datetime) -> bool:
    """调用方须先 expunge 该租约；过期条件无法在内存中对无时区时间求值，因此不同步会话。"""
    removed = await db.execute(_delete_expired_lease_stmt(lease_id, lease_token, now))
    return removed.rowcount == 1


def _delete_expired_lease_stmt(lease_id: int, lease_token: str, now: datetime):
    return (
        delete(DeviceLease)
        .where(DeviceLease.id == lease_id, DeviceLease.lease_token == lease_token, DeviceLease.expires_at <= now)
        .execution_options(synchronize_session=False)
    )


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
        if lease_is_active(current, now):
            raise DeviceLeaseConflict(_conflict_message(current, now))
        # SQLite 会复用 id，须带令牌；带过期条件则不会删掉持有者刚续期的租约。
        current_id, current_token = current.id, current.lease_token
        db.expunge(current)
        if not await _delete_expired_lease(db, current_id, current_token, now):
            # 没删到有两种可能：别人已接管或续期（冲突），或已被回收（设备空闲，继续）。
            if await _device_has_lease(db, device_id):
                raise DeviceLeaseConflict("设备已被其他任务占用")

    # 本地 SQLite（pysqlite 旧式事务）只在 DML 前隐式 BEGIN。先写设备状态，让下面的
    # SAVEPOINT 嵌套在调用方事务里；否则它成为最外层事务，RELEASE 时就提前提交了租约。
    # SQLite 下 FOR UPDATE 不生效，设备可能在读取后被置为离线或删除，这里要再判断一次。
    marked = await db.execute(
        update(Device)
        .where(Device.id == device_id, Device.status != DeviceStatus.offline)
        .values(status=DeviceStatus.busy)
    )
    if marked.rowcount != 1:
        status = (await db.execute(select(Device.status).where(Device.id == device_id))).scalar_one_or_none()
        if status is None:
            raise LookupError("设备不存在")
        raise DeviceLeaseConflict("设备当前离线，无法占用")
    device.status = DeviceStatus.busy
    lease = DeviceLease(
        device_id=device_id,
        lease_token=secrets.token_urlsafe(48),
        owner_id=owner_id,
        owner_label=owner_label,
        acquired_at=now,
        heartbeat_at=now,
        expires_at=now + timedelta(seconds=ttl_seconds),
    )
    try:
        # SQLite 没有行锁，互斥由 device_id 唯一约束兜底；保存点让冲突后调用方事务仍可用。
        async with db.begin_nested():
            db.add(lease)
            await db.flush()
    except IntegrityError:
        # 只有设备确实已有租约才算占用冲突；其他完整性错误（如 owner_id 外键）原样抛出。
        if await _device_has_lease(db, device_id):
            raise DeviceLeaseConflict("设备已被其他任务占用") from None
        raise
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
    now = _now()
    if lease is None or not lease_is_active(lease, now):
        raise DeviceLeaseConflict("设备租约不存在或已过期")
    expires_at = now + timedelta(seconds=ttl_seconds)
    # 读取之后租约可能到期并被接管；SQLite 还会复用 id，所以令牌和过期条件都要写进 UPDATE。
    renewed = await db.execute(
        update(DeviceLease)
        .where(DeviceLease.id == lease.id, DeviceLease.lease_token == lease_token, DeviceLease.expires_at > now)
        .values(heartbeat_at=now, expires_at=expires_at)
        .execution_options(synchronize_session=False)
    )
    if renewed.rowcount != 1:
        raise DeviceLeaseConflict("设备租约不存在或已过期")
    set_committed_value(lease, "heartbeat_at", now)
    set_committed_value(lease, "expires_at", expires_at)
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
    if lease is None or not lease_is_active(lease):
        return None
    return lease


async def release_device_lease(db: AsyncSession, device_id: int, lease_token: str) -> bool:
    # 一条语句按令牌删除：先读再按 id 删除时，SQLite 复用 id 会删掉接管者的新租约。
    removed = await db.execute(
        delete(DeviceLease).where(DeviceLease.device_id == device_id, DeviceLease.lease_token == lease_token)
    )
    if removed.rowcount != 1:
        return False
    device = await db.get(Device, device_id)
    if device is not None and device.status != DeviceStatus.offline:
        device.status = DeviceStatus.online
    await db.flush()
    return True


async def reclaim_expired_device_leases(db: AsyncSession) -> int:
    now = _now()
    expired = (await db.execute(select(DeviceLease).where(DeviceLease.expires_at <= now))).scalars().all()
    count = 0
    for lease in expired:
        device_id, lease_id, lease_token = lease.device_id, lease.id, lease.lease_token
        db.expunge(lease)
        # 已被接管或续期的租约不算过期，也不能把设备改回 online。
        if not await _delete_expired_lease(db, lease_id, lease_token, now):
            continue
        device = await db.get(Device, device_id)
        if device is not None and device.status == DeviceStatus.busy:
            device.status = DeviceStatus.online
        count += 1
    await db.flush()
    return count


def reclaim_expired_device_leases_sync(session: Session) -> int:
    """同步版本，逻辑与 reclaim_expired_device_leases 相同。

    供本地设备巡检在工作线程里使用：持有 SQLite 写锁的一方不能依赖主事件循环才能提交。
    """
    now = _now()
    expired = session.execute(select(DeviceLease).where(DeviceLease.expires_at <= now)).scalars().all()
    count = 0
    for lease in expired:
        device_id, lease_id, lease_token = lease.device_id, lease.id, lease.lease_token
        session.expunge(lease)
        # 已被接管或续期的租约不算过期，也不能把设备改回 online。
        if session.execute(_delete_expired_lease_stmt(lease_id, lease_token, now)).rowcount != 1:
            continue
        device = session.get(Device, device_id)
        if device is not None and device.status == DeviceStatus.busy:
            device.status = DeviceStatus.online
        count += 1
    session.flush()
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
