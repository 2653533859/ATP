"""本地模式设备巡检：定期扫描 ADB，同步设备状态并回收过期设备租约。

服务器模式由 Celery Beat 调度 ``scan_adb_devices`` 与 ``reclaim_expired_device_leases``。
本地模式不运行 Celery；没有本巡检时，设备状态只在手动扫描、连接或断开时刷新，
拔掉的设备会一直显示在线，过期租约也无人回收。
"""

from __future__ import annotations

import asyncio
import logging
from collections.abc import Awaitable, Callable

from sqlalchemy.orm import Session

from app.core.config import settings
from app.services.adb_service import AdbDeviceInfo, async_scan_devices
from app.services.device_leases import reclaim_expired_device_leases_sync
from app.services.device_sync import device_scan_lock, sync_devices_to_db_sync

logger = logging.getLogger(__name__)

MIN_INTERVAL_SECONDS = 5
MAX_BACKOFF_SECONDS = 120

Scanner = Callable[[], Awaitable[list[AdbDeviceInfo] | None]]
SessionFactory = Callable[[], Session]


def local_device_monitor_enabled() -> bool:
    """仅本地模式启用，可在本地档案里用 LOCAL_DEVICE_MONITOR_ENABLED=false 关闭。

    不看 ADB_SCAN_ENABLED：已有本地档案里它是 false，ADB_SCAN_MODE 在本地模式也读不到。
    """
    return bool(settings.ATP_LOCAL_MODE and settings.LOCAL_DEVICE_MONITOR_ENABLED)


def _apply_scan(session_factory: SessionFactory, scanned: list[AdbDeviceInfo]) -> None:
    """在工作线程里用同步引擎写库。

    写事务若开在主事件循环上（aiosqlite），每条语句都要回到事件循环才能继续；主循环线程上
    同步写库的代码（本地任务入队、远程 Agent 心跳）一旦撞上，会在 SQLite 忙等里卡住整个
    事件循环，巡检又因此无法提交，双方僵持到忙超时。放进工作线程后持锁方可以独立提交。
    """
    with session_factory() as session:
        # 先回收再同步，最终状态以本次扫描和剩余的有效租约为准。
        reclaim_expired_device_leases_sync(session)
        sync_devices_to_db_sync(session, scanned)
        session.commit()


async def scan_and_sync_once(session_factory: SessionFactory, scanner: Scanner = async_scan_devices) -> int | None:
    """扫描一次并写库；ADB 不可用时返回 None，不改任何状态。

    adb 调用期间不打开数据库事务。扫描锁与手动扫描、连接、断开接口共用，覆盖从扫描到提交的
    全过程，先开始的扫描不会晚提交、覆盖新结果。
    """
    async with device_scan_lock():
        scanned = await scanner()
        if scanned is None:
            return None
        await asyncio.to_thread(_apply_scan, session_factory, scanned)
    return len(scanned)


def _base_interval() -> int:
    return max(MIN_INTERVAL_SECONDS, int(settings.ADB_SCAN_INTERVAL))


def _next_delay(base: int, failures: int) -> float:
    """连续失败时指数退避，避免 ADB 缺失时每个周期都刷一遍告警日志。"""
    if failures <= 0:
        return base
    return min(MAX_BACKOFF_SECONDS, base * 2 ** min(failures - 1, 6))


async def run_local_device_monitor(
    stop_event: asyncio.Event,
    *,
    session_factory: SessionFactory | None = None,
    scanner: Scanner = async_scan_devices,
) -> None:
    """启动后立即巡检一次，之后按 ADB_SCAN_INTERVAL 重复，直到 stop_event 被设置。"""
    factory: SessionFactory
    if session_factory is None:
        from app.core.database import sync_session_factory

        factory = sync_session_factory
    else:
        factory = session_factory
    base = _base_interval()
    failures = 0
    while not stop_event.is_set():
        error: BaseException | None = None
        try:
            count = await scan_and_sync_once(factory, scanner)
        except Exception as exc:
            count, error = None, exc
        if count is None:
            if failures == 0:
                # 只在开始失败时告警一次；adb 每次调用失败的原因仍由 adb_service 记录。
                logger.warning("本地设备巡检失败，暂不更新设备状态，将退避重试", exc_info=error)
            failures += 1
        elif failures:
            logger.info("本地设备巡检已恢复")
            failures = 0
        try:
            await asyncio.wait_for(stop_event.wait(), timeout=_next_delay(base, failures))
        except asyncio.TimeoutError:
            pass
