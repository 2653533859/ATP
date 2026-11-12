"""设备已安装包名快照：写入、读取与历史查询。

读取动作走后台任务，页面只读快照；快照同时充当缓存与历史记录。
"""

import logging
from datetime import datetime, timezone

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.device import DevicePackageSnapshot

logger = logging.getLogger(__name__)

SNAPSHOT_STALE_SECONDS = 600
SNAPSHOT_HISTORY_LIMIT = 50


def _utc(value: datetime | None) -> datetime | None:
    if value is None:
        return None
    return value if value.tzinfo else value.replace(tzinfo=timezone.utc)


def snapshot_age_seconds(snapshot: DevicePackageSnapshot, now: datetime | None = None) -> float | None:
    read_at = _utc(snapshot.read_at)
    if read_at is None:
        return None
    return ((now or datetime.now(timezone.utc)) - read_at).total_seconds()


def serialize_snapshot(snapshot: DevicePackageSnapshot) -> dict[str, object]:
    """把快照转成接口返回结构；超过 10 分钟的读取标记为 stale。"""
    age = snapshot_age_seconds(snapshot)
    return {
        "device_id": snapshot.device_id,
        "serial": snapshot.serial,
        "current_package": snapshot.current_package,
        "current_activity": snapshot.current_activity,
        "packages": list(snapshot.packages or []),
        "read_at": snapshot.read_at,
        "stale": age is None or age > SNAPSHOT_STALE_SECONDS,
        "source": snapshot.source,
    }


async def latest_snapshot(db: AsyncSession, device_id: int) -> DevicePackageSnapshot | None:
    return await db.scalar(
        select(DevicePackageSnapshot)
        .where(DevicePackageSnapshot.device_id == device_id)
        .order_by(DevicePackageSnapshot.id.desc())
        .limit(1)
    )


async def list_snapshots(db: AsyncSession, device_id: int, limit: int = 10) -> list[DevicePackageSnapshot]:
    result = await db.execute(
        select(DevicePackageSnapshot)
        .where(DevicePackageSnapshot.device_id == device_id)
        .order_by(DevicePackageSnapshot.id.desc())
        .limit(max(1, min(limit, SNAPSHOT_HISTORY_LIMIT)))
    )
    return list(result.scalars().all())


async def save_snapshot(
    db: AsyncSession,
    *,
    device_id: int,
    serial: str,
    payload: dict[str, object],
    source: str = "manual",
    triggered_by: int | None = None,
    read_at: datetime | None = None,
) -> DevicePackageSnapshot:
    raw_packages = payload.get("packages")
    packages = [str(item) for item in raw_packages] if isinstance(raw_packages, list) else []
    current_package = payload.get("current_package")
    current_activity = payload.get("current_activity")
    snapshot = DevicePackageSnapshot(
        device_id=device_id,
        serial=serial,
        current_package=str(current_package) if isinstance(current_package, str) and current_package else None,
        current_activity=str(current_activity) if isinstance(current_activity, str) and current_activity else None,
        packages=packages,
        source=source,
        triggered_by=triggered_by,
        read_at=read_at or datetime.now(timezone.utc),
    )
    db.add(snapshot)
    await db.flush()
    await _prune_history(db, device_id)
    return snapshot


async def _prune_history(db: AsyncSession, device_id: int) -> None:
    """每个设备只保留最近 N 条快照，避免历史表无界增长。"""
    stale_ids = (
        (
            await db.execute(
                select(DevicePackageSnapshot.id)
                .where(DevicePackageSnapshot.device_id == device_id)
                .order_by(DevicePackageSnapshot.id.desc())
                .offset(SNAPSHOT_HISTORY_LIMIT)
            )
        )
        .scalars()
        .all()
    )
    if stale_ids:
        await db.execute(delete(DevicePackageSnapshot).where(DevicePackageSnapshot.id.in_(stale_ids)))
