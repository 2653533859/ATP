"""
设备同步服务 — 将 ADB 扫描结果同步到数据库

提供 sync（Celery 任务）和 async（API 端点）两个版本，
共享同一套 upsert + offline 标记逻辑。
"""

from datetime import datetime, timezone

from sqlalchemy import case, func, literal, update
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Session

from app.models.device import Device, DeviceStatus
from app.services.adb_service import AdbDeviceInfo


def _build_upsert_stmt(info: AdbDeviceInfo, now: datetime):
    """构建按 serial 原子 upsert 的 SQL 语句（PostgreSQL ON CONFLICT）"""
    new_status = DeviceStatus.online if info.status == "device" else DeviceStatus.offline
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
            "status": case(
                (Device.status != DeviceStatus.busy, literal(new_status, type_=Device.status.type)),
                else_=Device.status,
            ),
            "last_seen_at": now,
        },
    )


def sync_devices_to_db_sync(session: Session, scanned: list[AdbDeviceInfo]) -> None:
    """同步版本（供 Celery 任务使用）"""
    now = datetime.now(timezone.utc)
    scanned_serials = {info.serial for info in scanned}

    for info in scanned:
        session.execute(_build_upsert_stmt(info, now))

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

    for info in scanned:
        await db.execute(_build_upsert_stmt(info, now))

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
