"""
Celery 定时任务：ADB 设备扫描

由 Celery Beat 按 ADB_SCAN_INTERVAL 调度，
扫描已连接设备并更新数据库状态。
"""

import base64
import logging
import socket
import time

from sqlalchemy import select

from app.worker.celery_app import celery_app
from app.services.adb_service import (
    async_connect_remote_device,
    async_disconnect_remote_device,
    scan_devices,
)
from app.services.android_worker_registry import (
    _prefix as _registry_prefix,
    _sync_redis_client,
    acquire_worker_scan_lock_sync,
    list_android_workers,
    register_android_worker,
    release_worker_scan_lock_sync,
    verify_worker_execution_target,
    worker_android_queue,
    worker_key,
)
from app.services.device_sync import mark_worker_devices_offline_sync, sync_devices_to_db_sync
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


def _reconcile_offline_worker_devices(online_worker_ids: set[str]) -> list[str]:
    """Converge devices of workers missing past the grace period to offline.

    Only called after ``list_android_workers()`` succeeds, so a Redis outage
    never misjudges live workers as offline. Re-checks ``worker_key(wid)``
    before writing to avoid clobbering a worker that just reconnected.
    """
    from redis.exceptions import RedisError

    from app.core.config import settings
    from app.core.database import sync_session_factory
    from app.models.device import Device, DeviceStatus

    local_owner = settings.ANDROID_LOCAL_OWNER_ID.strip() or "local"
    grace_seconds = max(0, int(settings.ANDROID_WORKER_OFFLINE_GRACE_SECONDS))
    converged: list[str] = []

    session = sync_session_factory()
    redis_client = None
    try:
        rows = session.execute(
            select(Device.worker_id)
            .where(Device.worker_id.is_not(None))
            .where(Device.status != DeviceStatus.offline)
            .distinct()
        )
        scalars_fn = getattr(rows, "scalars", None)
        active_db_workers = (
            [str(w).strip() for w in scalars_fn().all() if w and str(w).strip()] if callable(scalars_fn) else []
        )
        if not active_db_workers:
            return []

        redis_client = _sync_redis_client()
        now = time.time()
        missing_ttl = max(300, grace_seconds * 10 + 60)

        for wid in active_db_workers:
            if wid == local_owner or wid.startswith(("tunnel:", "tunnel.")):
                continue
            missing_key = f"{_registry_prefix()}:missing:{wid}"
            if wid in online_worker_ids:
                redis_client.delete(missing_key)
                continue

            raw_since = redis_client.get(missing_key)
            if raw_since is None:
                redis_client.set(missing_key, str(now), ex=missing_ttl, nx=True)
                if grace_seconds > 0:
                    continue
            else:
                try:
                    missing_since = float(raw_since)
                except (TypeError, ValueError):
                    redis_client.set(missing_key, str(now), ex=missing_ttl)
                    if grace_seconds > 0:
                        continue
                    missing_since = now
                if now - missing_since < grace_seconds:
                    continue

            # Secondary confirmation after grace period: verify worker did not reconnect.
            if redis_client.get(worker_key(wid)):
                redis_client.delete(missing_key)
                continue

            updated = mark_worker_devices_offline_sync(session, wid)
            if updated > 0:
                converged.append(wid)
            redis_client.delete(missing_key)

        if converged:
            session.commit()
            logger.info("Converged devices offline for lost Android Worker(s): %s", ", ".join(converged))
        return converged
    except RedisError:
        session.rollback()
        logger.warning("Redis unavailable during offline worker device reconciliation; skipping")
        return []
    except Exception:
        session.rollback()
        logger.warning("Offline worker device reconciliation skipped due to error", exc_info=True)
        return []
    finally:
        if redis_client is not None:
            close_fn = getattr(redis_client, "close", None)
            if callable(close_fn):
                try:
                    close_fn()
                except Exception:
                    pass
        session.close()


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
        online_ids = {
            str(item.get("worker_id") or "").strip() for item in workers if str(item.get("worker_id") or "").strip()
        }
        if settings.ANDROID_MULTI_NODE_ENABLED:
            _reconcile_offline_worker_devices(online_ids)
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

    lock_client = None
    lock_token = None
    if active_worker_id and settings.ANDROID_MULTI_NODE_ENABLED and settings.ADB_SCAN_MODE.strip().lower() == "worker":
        try:
            lock_client = _sync_redis_client()
            lock_token = acquire_worker_scan_lock_sync(
                lock_client,
                active_worker_id,
                ttl_seconds=max(30, int(settings.ADB_SCAN_INTERVAL) * 2),
            )
            if lock_token is None:
                return {"status": "skipped_concurrent", "worker_id": active_worker_id, "count": 0}
        except Exception:
            logger.debug("Per-worker scan lock unavailable for %s; proceeding inline", active_worker_id)
            if lock_client is not None:
                close_fn = getattr(lock_client, "close", None)
                if callable(close_fn):
                    try:
                        close_fn()
                    except Exception:
                        pass
                lock_client = None

    from app.core.database import sync_session_factory

    try:
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
    finally:
        if lock_client is not None and active_worker_id and lock_token:
            try:
                release_worker_scan_lock_sync(lock_client, active_worker_id, lock_token=lock_token)
            except Exception:
                pass
            close_fn = getattr(lock_client, "close", None)
            if callable(close_fn):
                try:
                    close_fn()
                except Exception:
                    pass


def _verify_worker_write_lease_sync(
    *,
    device_id: int,
    expected_worker_id: str | None,
    lease_token: str | None,
) -> tuple[bool, str | None]:
    """Re-verify device ownership and active lease right before executing a mutating ADB action."""
    from datetime import datetime, timezone

    from app.core.database import sync_session_factory
    from app.models.device import Device, DeviceLease

    session = sync_session_factory()
    try:
        device = session.get(Device, device_id)
        if device is None:
            return False, "device_not_found: 设备不存在"
        if expected_worker_id and (device.worker_id or "").strip() != expected_worker_id.strip():
            return False, "worker_id_mismatch: 设备归属已变更，拒绝执行旧控制指令"
        if not lease_token:
            return False, "lease_required: 缺少有效设备控制租约"
        now = datetime.now(timezone.utc)
        lease = session.scalar(
            select(DeviceLease).where(
                DeviceLease.device_id == device_id,
                DeviceLease.lease_token == lease_token,
            )
        )
        if lease is None:
            return False, "lease_expired: 设备控制租约不存在或已被释放"
        expires_at = lease.expires_at
        if expires_at is not None:
            if expires_at.tzinfo is None:
                expires_at = expires_at.replace(tzinfo=timezone.utc)
            if expires_at <= now:
                return False, "lease_expired: 设备控制租约已过期"
        return True, None
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
        from app.core.config import settings

        if settings.ANDROID_MULTI_NODE_ENABLED and not settings.ATP_LOCAL_MODE and params.get("device_id") is not None:
            ok_lease, lease_err = _verify_worker_write_lease_sync(
                device_id=int(params["device_id"]),
                expected_worker_id=str(expected_worker_id) if expected_worker_id else None,
                lease_token=str(params["lease_token"]) if params.get("lease_token") else None,
            )
            if not ok_lease:
                return {"ok": False, "error": lease_err}

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
