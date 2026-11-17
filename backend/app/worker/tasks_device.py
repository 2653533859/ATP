"""
Celery 定时任务：ADB 设备扫描

由 Celery Beat 按 ADB_SCAN_INTERVAL 调度，
扫描已连接设备并更新数据库状态。
"""

import base64
import logging
import socket

from app.worker.celery_app import celery_app
from app.services.adb_service import (
    async_connect_remote_device,
    async_disconnect_remote_device,
    scan_devices,
)
from app.services.android_worker_registry import (
    list_android_workers,
    register_android_worker,
    verify_worker_execution_target,
    worker_android_queue,
)
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
    execution_queue = settings.ANDROID_WORKER_QUEUE.strip() or "mobile_special"
    target_queues = (
        [worker_android_queue(worker_id), f"{execution_queue}.{worker_id}"]
        if settings.ANDROID_MULTI_NODE_ENABLED
        else ["android", execution_queue]
    )
    reschedule_queue = worker_android_queue(worker_id) if settings.ANDROID_MULTI_NODE_ENABLED else "android"

    try:
        payload = run_async(register_android_worker(worker_id, queues=target_queues))
    except Exception:
        logger.exception("Android Worker heartbeat failed for %s", worker_id)
        payload = {"status": "failed", "worker_id": worker_id}
    finally:
        self.apply_async(
            countdown=max(5, int(settings.ANDROID_WORKER_HEARTBEAT_SECONDS)),
            queue=reschedule_queue,
        )
    return payload


@celery_app.task(name="dispatch_android_device_scan", ignore_result=True)
def dispatch_android_device_scan():
    """Queue periodic scans only while an eligible worker can consume them.

    Celery Beat runs on Linux where ADB is unavailable. In remote-worker mode
    it checks the TTL registry first, preventing an unbounded Redis backlog
    while the Windows Android Worker is offline. Local mode keeps periodic
    scans for an all-in-one worker that consumes the ``android`` queue.
    """
    from app.core.config import settings

    if not settings.ADB_SCAN_ENABLED:
        return {"status": "disabled"}

    mode = settings.ADB_SCAN_MODE.strip().lower()
    if mode == "worker":
        try:
            workers = run_async(list_android_workers())
        except Exception:
            logger.exception("Unable to inspect Android Worker registry before periodic scan")
            return {"status": "registry_unavailable"}
        if not workers:
            return {"status": "no_worker"}
        if settings.ANDROID_MULTI_NODE_ENABLED:
            ttl = max(15, int(settings.ADB_SCAN_INTERVAL))
            dispatched: list[str] = []
            for item in workers:
                wid = str(item.get("worker_id") or "").strip()
                if not wid:
                    continue
                gen = item.get("instance_generation")
                scan_adb_devices.apply_async(
                    kwargs={"worker_id": wid, "expected_generation": gen},
                    queue=worker_android_queue(wid),
                    ignore_result=True,
                    expires=ttl,
                )
                dispatched.append(wid)
            return {"status": "queued", "workers": dispatched}
    elif mode != "local":
        return {"status": "disabled"}

    scan_adb_devices.apply_async(
        queue="android",
        ignore_result=True,
        expires=max(5, int(settings.ADB_SCAN_INTERVAL)),
    )
    return {"status": "queued"}


@celery_app.task(name="scan_adb_devices")
def scan_adb_devices(worker_id: str | None = None, expected_generation: int | None = None):
    """同步任务：扫描 ADB 设备并更新数据库"""
    from app.core.config import settings

    if not settings.ADB_SCAN_ENABLED:
        return {"status": "failed", "error": "ADB 扫描已被配置关闭", "count": 0}

    ok_target, reject_reason = verify_worker_execution_target(
        expected_worker_id=worker_id,
        expected_generation=expected_generation,
    )
    if not ok_target:
        return {"status": "rejected", "error": reject_reason, "count": 0}

    active_worker_id = settings.ANDROID_WORKER_ID.strip() or (
        settings.ANDROID_LOCAL_OWNER_ID.strip() or "local"
        if settings.ADB_SCAN_MODE.strip().lower() == "local"
        else None
    )

    from app.core.database import sync_session_factory

    scanned = scan_devices()
    if scanned is None:
        logger.warning("ADB scan failed; skipping device status synchronization")
        return {"status": "failed", "error": "ADB 扫描失败", "count": 0}

    session = sync_session_factory()
    try:
        if active_worker_id is not None:
            sync_devices_to_db_sync(
                session,
                scanned,
                worker_id=active_worker_id,
                worker_hostname=socket.gethostname(),
            )
        else:
            sync_devices_to_db_sync(session, scanned)
        session.commit()
        if scanned:
            logger.debug("Device scan completed: %d device(s) found", len(scanned))
        return {"status": "completed", "count": len(scanned), "worker_id": active_worker_id}
    except Exception:
        session.rollback()
        logger.exception("Device scan task failed")
        return {"status": "failed", "error": "设备扫描结果写入数据库失败", "count": 0}
    finally:
        session.close()


@celery_app.task(name="run_android_device_operation")
def run_android_device_operation(operation: str, serial: str, params: dict | None = None):
    """在 Android Worker 所在机器执行受控的设备交互操作。

    API 部署在公网时不能访问用户电脑的 ADB；任务通过专属队列落到对应 Windows Worker，
    返回值只包含 JSON 可序列化的数据。
    """
    params = dict(params or {})
    if operation not in {
        "screenshot",
        "tap",
        "swipe",
        "ui_target",
        "ui_anchors",
        "keyevent",
        "text",
        "packages",
        "connect",
        "disconnect",
    }:
        return {"ok": False, "error": f"不支持的 Android 设备操作: {operation}"}
    if not serial.strip():
        return {"ok": False, "error": "设备 serial 不能为空"}

    expected_worker_id = params.get("expected_worker_id")
    expected_generation = params.get("expected_generation")
    ok_target, reject_reason = verify_worker_execution_target(
        expected_worker_id=str(expected_worker_id) if expected_worker_id else None,
        expected_generation=int(expected_generation) if expected_generation is not None else None,
    )
    if not ok_target:
        return {"ok": False, "error": reject_reason}

    try:
        if operation == "connect":
            host = str(params.get("host") or "").strip()
            port = int(params.get("port") or 5555)
            success, message = run_async(async_connect_remote_device(host, port))
            return {"ok": bool(success), "message": message, "error": None if success else message}

        if operation == "disconnect":
            success, message = run_async(async_disconnect_remote_device(serial.strip()))
            return {"ok": bool(success), "message": message, "error": None if success else message}
        # 延迟导入避免 Celery 启动时把 FastAPI 路由模块作为强依赖加载，也便于按操作隔离测试替身。
        if operation == "screenshot":
            from app.api.v1.device_mirror import _adb_screenshot

            data = _adb_screenshot(serial)
            return {
                "ok": bool(data),
                "data_base64": base64.b64encode(data).decode("ascii") if data else None,
                "error": None if data else "ADB 截图失败",
            }

        if operation == "ui_target":
            from app.api.v1.device_mirror import _adb_ui_target_diagnostic

            target, diagnostic = _adb_ui_target_diagnostic(serial, int(params["x"]), int(params["y"]))
            return {"ok": True, "target": target, "diagnostic": diagnostic}

        if operation == "ui_anchors":
            from app.api.v1.device_mirror import _adb_ui_anchors_diagnostic

            anchors, diagnostic = _adb_ui_anchors_diagnostic(serial)
            return {"ok": True, "anchors": anchors, "diagnostic": diagnostic}

        if operation == "packages":
            from app.api.v1.device_mirror import _adb_device_packages

            info = _adb_device_packages(serial, include_system=bool(params.get("include_system", False)))
            if info is None:
                return {"ok": False, "error": "ADB 获取设备包名列表失败"}
            return {"ok": True, **info}

        from app.api.v1.device_mirror import _adb_input

        if operation == "tap":
            args = ["tap", str(int(params["x"])), str(int(params["y"]))]
        elif operation in {"keyevent", "text"}:
            args = [operation, str(params["keycode" if operation == "keyevent" else "text"])]
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
