"""
Celery 定时任务：ADB 设备扫描

由 Celery Beat 按 ADB_SCAN_INTERVAL 调度，
扫描已连接设备并更新数据库状态。
"""

import base64
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


@celery_app.task(name="run_android_device_operation")
def run_android_device_operation(operation: str, serial: str, params: dict | None = None):
    """在 Android Worker 所在机器执行受控的设备交互操作。

    API 部署在公网时不能访问用户电脑的 ADB；任务通过 ``mobile_special``
    队列落到 Windows Worker，返回值只包含 JSON 可序列化的数据。
    """
    params = params or {}
    if operation not in {"screenshot", "tap", "swipe", "ui_target"}:
        return {"ok": False, "error": f"不支持的 Android 设备操作: {operation}"}
    if not serial.strip():
        return {"ok": False, "error": "设备 serial 不能为空"}

    try:
        # 延迟导入避免 Celery 启动时把 FastAPI 路由模块作为强依赖加载。
        from app.api.v1.device_mirror import _adb_input, _adb_screenshot, _adb_ui_target

        if operation == "screenshot":
            data = _adb_screenshot(serial)
            return {
                "ok": bool(data),
                "data_base64": base64.b64encode(data).decode("ascii") if data else None,
                "error": None if data else "ADB 截图失败",
            }

        if operation == "ui_target":
            target = _adb_ui_target(serial, int(params["x"]), int(params["y"]))
            return {"ok": True, "target": target}

        if operation == "tap":
            args = ["tap", str(int(params["x"])), str(int(params["y"]))]
        else:
            duration_ms = max(100, min(int(params.get("duration_ms", 300)), 5000))
            args = [
                "swipe",
                str(int(params["x1"])),
                str(int(params["y1"])),
                str(int(params["x2"])),
                str(int(params["y2"])),
                str(duration_ms),
            ]
        ok = _adb_input(serial, *args)
        return {"ok": bool(ok), "error": None if ok else f"ADB {operation} 失败"}
    except (KeyError, TypeError, ValueError) as exc:
        return {"ok": False, "error": f"设备操作参数无效: {exc}"}
    except Exception as exc:
        logger.exception("Android device operation failed: %s %s", operation, serial)
        return {"ok": False, "error": str(exc)[:500]}
