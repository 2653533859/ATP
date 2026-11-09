"""
设备同步服务 — 将 ADB 扫描结果同步到数据库

提供 sync（Celery 任务、本地设备巡检的工作线程）和 async（API 端点）两个版本，
共享同一套 upsert + offline 标记逻辑。
"""

import asyncio
import weakref
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import ColumnElement, case, exists, func, literal, update
from sqlalchemy.dialects.postgresql import insert as postgres_insert
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Session

from app.models.device import Device, DeviceLease, DeviceStatus
from app.services.adb_service import AdbDeviceInfo

_scan_locks: "weakref.WeakKeyDictionary[asyncio.AbstractEventLoop, asyncio.Lock]" = weakref.WeakKeyDictionary()


def device_scan_lock() -> asyncio.Lock:
    """串行化同一进程内的“扫描 → 同步 → 提交”。

    本地模式下后台巡检与手动扫描、连接、断开共用一个事件循环；不串行化时，先开始的扫描
    可能后提交，用旧结果覆盖刚写入的新状态。按事件循环各建一把锁，避免锁绑定到别的循环。
    """
    loop = asyncio.get_running_loop()
    lock = _scan_locks.get(loop)
    if lock is None:
        lock = _scan_locks[loop] = asyncio.Lock()
    return lock


def _build_upsert_stmt(info: AdbDeviceInfo, now: datetime, dialect_name: str = "postgresql"):
    """构建按 serial 原子 upsert 的 SQL 语句。

    adb 报告的不是 device 状态就是离线，占用中的设备也一样，掉线后不能继续显示占用中。
    device 状态时只把离线改为在线；在线与占用中的区分交给 _reconcile_busy_stmts 按租约判定。
    """
    online = info.status == "device"
    new_status = DeviceStatus.online if online else DeviceStatus.offline
    status_type = Device.status.type
    status_on_conflict: ColumnElement[Any]
    if online:
        status_on_conflict = case(
            (Device.status == DeviceStatus.offline, literal(DeviceStatus.online, type_=status_type)),
            else_=Device.status,
        )
    else:
        status_on_conflict = literal(DeviceStatus.offline, type_=status_type)
    insert = sqlite_insert if dialect_name == "sqlite" else postgres_insert
    stmt = insert(Device).values(
        serial=info.serial,
        name=info.model or info.serial,
        model=info.model,
        brand=info.brand,
        os_version=info.os_version,
        sdk_version=info.sdk_version,
        resolution=info.resolution,
        status=new_status,
        ip_address=info.ip_address,
        port=info.port,
        last_seen_at=now,
    )
    excluded = stmt.excluded
    return stmt.on_conflict_do_update(
        index_elements=[Device.serial],
        set_={
            "model": func.coalesce(excluded.model, Device.model),
            "brand": func.coalesce(excluded.brand, Device.brand),
            "os_version": func.coalesce(excluded.os_version, Device.os_version),
            "sdk_version": func.coalesce(excluded.sdk_version, Device.sdk_version),
            "resolution": func.coalesce(excluded.resolution, Device.resolution),
            "ip_address": func.coalesce(excluded.ip_address, Device.ip_address),
            "port": func.coalesce(excluded.port, Device.port),
            "status": status_on_conflict,
            "last_seen_at": now,
        },
    )


def _reconcile_busy_stmts(online_serials: set[str], now: datetime) -> tuple:
    """在线设备持有未过期租约才算占用中；只改状态确实变化的行。

    子查询放在普通 UPDATE 里，SQLAlchemy 会把它关联到当前设备行；放进 ON CONFLICT DO UPDATE
    时不会关联，会变成“任意设备有租约”。按扫描时刻判定，并发获取或释放租约造成的偏差
    在下次扫描时自动纠正。
    """
    holds_lease = exists().where(DeviceLease.device_id == Device.id, DeviceLease.expires_at > now)
    in_scan = Device.serial.in_(online_serials)
    return (
        update(Device)
        .where(in_scan, Device.status == DeviceStatus.online, holds_lease)
        .values(status=DeviceStatus.busy)
        .execution_options(synchronize_session=False),
        update(Device)
        .where(in_scan, Device.status == DeviceStatus.busy, ~holds_lease)
        .values(status=DeviceStatus.online)
        .execution_options(synchronize_session=False),
    )


def _online_serials(scanned: list[AdbDeviceInfo]) -> set[str]:
    return {info.serial for info in scanned if info.status == "device"}


def sync_devices_to_db_sync(session: Session, scanned: list[AdbDeviceInfo]) -> None:
    """同步版本（供 Celery 任务与本地设备巡检的工作线程使用）"""
    now = datetime.now(timezone.utc)
    scanned_serials = {info.serial for info in scanned}

    dialect_name = session.get_bind().dialect.name
    for info in scanned:
        session.execute(_build_upsert_stmt(info, now, dialect_name))
    online_serials = _online_serials(scanned)
    if online_serials:
        for stmt in _reconcile_busy_stmts(online_serials, now):
            session.execute(stmt)

    # 将未扫描到的非 offline 设备标记为 offline（批量 UPDATE）
    if scanned_serials:
        session.execute(
            update(Device)
            .where(Device.serial.not_in(scanned_serials))
            .where(Device.status != DeviceStatus.offline)
            .values(status=DeviceStatus.offline)
        )
    else:
        session.execute(update(Device).where(Device.status != DeviceStatus.offline).values(status=DeviceStatus.offline))


async def sync_devices_to_db_async(db: AsyncSession, scanned: list[AdbDeviceInfo]) -> None:
    """异步版本（供 API 端点使用）"""
    now = datetime.now(timezone.utc)
    scanned_serials = {info.serial for info in scanned}

    dialect_name = db.get_bind().dialect.name
    for info in scanned:
        await db.execute(_build_upsert_stmt(info, now, dialect_name))
    online_serials = _online_serials(scanned)
    if online_serials:
        for stmt in _reconcile_busy_stmts(online_serials, now):
            await db.execute(stmt)

    if scanned_serials:
        await db.execute(
            update(Device)
            .where(Device.serial.not_in(scanned_serials))
            .where(Device.status != DeviceStatus.offline)
            .values(status=DeviceStatus.offline)
        )
    else:
        await db.execute(
            update(Device).where(Device.status != DeviceStatus.offline).values(status=DeviceStatus.offline)
        )
