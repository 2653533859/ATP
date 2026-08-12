"""
Celery 定时任务：ADB 设备扫描

由 Celery Beat 按 ADB_SCAN_INTERVAL 调度，
扫描已连接设备并更新数据库状态。
"""

import logging

from app.worker.celery_app import celery_app
from app.services.adb_service import scan_devices
from app.services.android_worker_registry import register_android_worker
from app.services.device_sync import sync_devices_to_db_sync
from app.worker.async_runner import run_async

logger = logging.getLogger(__name__)


@celery_app.task(bind=True, name="heartbeat_android_worker", ignore_result=True)
def heartbeat_android_worker(self):
    """Refresh the Windows Android Worker registry and schedule the next heartbeat."""
    from app.core.config import settings

    worker_id = settings.ANDROID_WORKER_ID.strip()
    if not worker_id:
        return {"status": "disabled"}
    queue = settings.ANDROID_WORKER_QUEUE.strip() or "mobile_special"

    try:
        payload = run_async(register_android_worker(worker_id, queues=[queue]))
    except Exception:
        logger.exception("Android Worker heartbeat failed for %s", worker_id)
        payload = {"status": "failed", "worker_id": worker_id}
    finally:
        self.apply_async(
            countdown=max(5, int(settings.ANDROID_WORKER_HEARTBEAT_SECONDS)),
            queue=queue,
        )
    return payload


@celery_app.task(name="scan_adb_devices", ignore_result=True)
def scan_adb_devices():
    """同步任务：扫描 ADB 设备并更新数据库"""
    from app.core.config import settings

    if not settings.ADB_SCAN_ENABLED:
        return {"status": "failed", "error": "ADB 扫描已被配置关闭", "count": 0}

    from app.core.database import sync_session_factory

    scanned = scan_devices()
    if scanned is None:
        logger.warning("ADB scan failed; skipping device status synchronization")
        return {"status": "failed", "error": "ADB 扫描失败", "count": 0}

    session = sync_session_factory()
    try:
        sync_devices_to_db_sync(session, scanned)
        session.commit()
        if scanned:
            logger.debug("Device scan completed: %d device(s) found", len(scanned))
        return {"status": "completed", "count": len(scanned)}
    except Exception:
        session.rollback()
        logger.exception("Device scan task failed")
        return {"status": "failed", "error": "设备扫描结果写入数据库失败", "count": 0}
    finally:
        session.close()
