"""
Celery 定时任务：ADB 设备扫描

由 Celery Beat 按 ADB_SCAN_INTERVAL 调度，
扫描已连接设备并更新数据库状态。
"""

import logging

from app.worker.celery_app import celery_app
from app.services.adb_service import scan_devices
from app.services.device_sync import sync_devices_to_db_sync

logger = logging.getLogger(__name__)


@celery_app.task(name="scan_adb_devices", ignore_result=True)
def scan_adb_devices():
    """同步任务：扫描 ADB 设备并更新数据库"""
    from app.core.config import settings

    if not settings.ADB_SCAN_ENABLED:
        return

    from app.core.database import sync_session_factory

    scanned = scan_devices()
    if scanned is None:
        logger.warning("ADB scan failed; skipping device status synchronization")
        return

    session = sync_session_factory()
    try:
        sync_devices_to_db_sync(session, scanned)
        session.commit()
        if scanned:
            logger.debug("Device scan completed: %d device(s) found", len(scanned))
    except Exception:
        session.rollback()
        logger.exception("Device scan task failed")
    finally:
        session.close()
