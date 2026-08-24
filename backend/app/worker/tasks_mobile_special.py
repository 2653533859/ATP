"""Celery tasks for mobile special testing domain."""

from datetime import datetime, timezone
from typing import Any

from app.worker.celery_app import celery_app
from app.worker.async_runner import run_async
from app.models.bootstrap import load_all_models
from app.core.redis_client import publish_run_event
from app.services.device_leases import (
    DeviceLeaseConflict,
    acquire_device_lease,
    release_device_lease,
)
from app.services.mobile_special_control import clear_cancel_request, is_cancel_requested
from app.services.performance_control import create_control_client
from app.services.mobile_special_events import MobileRunEventRecorder
import logging

logger = logging.getLogger(__name__)

load_all_models()


async def _safe_publish_run_event(run_id: int, payload: dict) -> None:
    try:
        await publish_run_event(run_id, payload, run_type="mobile")
    except Exception:
        logger.exception(f"Failed to publish event for run {run_id}")


@celery_app.task(bind=True, name="run_mobile_special_task")
def run_mobile_special_task(self, run_id: int):
    """统一执行入口，根据 task_type 路由到对应 executor"""
    from app.core.database import AsyncSessionLocal
    from app.models.mobile_special import MobileSpecialRun, MobileSpecialTask, RunStatus, TaskType

    control_client = create_control_client()

    async def _execute():
        async with AsyncSessionLocal() as db:
            run = await db.get(MobileSpecialRun, run_id)
            if not run:
                logger.error(f"MobileSpecialRun {run_id} not found")
                return
            events = MobileRunEventRecorder(db, run_id)
            await events.initialize()
            await events.record(
                event_type="run_received",
                phase="dispatch",
                action="load_run",
                parameters={"run_id": run_id},
                result={"status": run.status.value if hasattr(run.status, "value") else str(run.status)},
            )
            if run.status == RunStatus.stopped or is_cancel_requested(run_id, client=control_client):
                run.status = RunStatus.stopped
                run.finished_at = run.finished_at or datetime.now(timezone.utc)
                await db.commit()
                await events.record(
                    event_type="run_stopped",
                    phase="dispatch",
                    action="cancel_before_start",
                    result={"status": RunStatus.stopped.value},
                )
                return

            task = await db.get(MobileSpecialTask, run.task_id)
            if not task:
                run.status = RunStatus.failed
                run.summary_json = {"error_message": "Task not found"}
                await db.commit()
                await events.record(
                    event_type="dispatch_error",
                    phase="dispatch",
                    level="error",
                    message="Task not found",
                    result={"ok": False},
                )
                return

            run.config_snapshot = _merge_run_config(task.config_json, run.config_snapshot)
            run.task_type = task.task_type
            run.device_id = _resolve_run_device_id(run, task)
            run.apk_id = run.apk_id or task.apk_id
            run.app_package = _resolve_run_app_package(run, task)
            run.device_serial = run.config_snapshot.get("device_serial") or await _get_device_serial(db, run.device_id)
            if run.device_serial:
                run.config_snapshot["device_serial"] = run.device_serial
            await db.commit()
            await events.record(
                event_type="configuration",
                phase="device_setup",
                action="resolve_run_config",
                parameters={
                    "task_type": task.task_type.value,
                    "device_id": run.device_id,
                    "device_serial": run.device_serial,
                    "app_package": run.app_package,
                },
                result={"ok": True},
            )
            lease_token: str | None = None
            if run.device_id is not None:
                try:
                    lease = await acquire_device_lease(
                        db,
                        run.device_id,
                        owner_id=run.triggered_by,
                        owner_label=f"mobile-run:{run_id}",
                        ttl_seconds=max(900, int(run.config_snapshot.get("device_lease_ttl_seconds", 900))),
                    )
                    lease_token = lease.lease_token
                    await db.commit()
                    await events.record(
                        event_type="device_lease",
                        phase="device_setup",
                        action="acquire_device_lease",
                        level="info",
                        message="设备租约获取成功",
                        result={"ok": True, "lease_acquired": True},
                    )
                except (DeviceLeaseConflict, LookupError) as exc:
                    run.status = RunStatus.failed
                    run.finished_at = datetime.now(timezone.utc)
                    run.summary_json = {"error_message": f"设备租约冲突: {exc}"}
                    await db.commit()
                    await events.record(
                        event_type="device_lease",
                        phase="device_setup",
                        action="acquire_device_lease",
                        level="error",
                        message="设备租约获取失败",
                        result={"ok": False, "lease_acquired": False, "error": str(exc)[:500]},
                    )
                    await _safe_publish_run_event(
                        run_id,
                        {
                            "type": "log",
                            "run_id": run_id,
                            "level": "error",
                            "message": f"设备租约获取失败：{exc}",
                        },
                    )
                    await _safe_publish_run_event(
                        run_id,
                        {
                            "type": "completed",
                            "run_id": run_id,
                            "status": "failed",
                            "progress": 100,
                            "current_step": "设备租约获取失败",
                            "device_status": "offline",
                            "error": str(exc)[:500],
                        },
                    )
                    return

            try:
                await _safe_publish_run_event(
                    run_id,
                    {
                        "type": "run_status",
                        "run_id": run_id,
                        "status": "running",
                        "phase": "device_setup",
                        "progress": 15,
                        "current_step": "连接 Android 设备",
                        "device_serial": run.device_serial,
                        "device_status": "online" if run.device_serial else "unknown",
                    },
                )
                await _safe_publish_run_event(
                    run_id,
                    {
                        "type": "log",
                        "run_id": run_id,
                        "level": "info",
                        "message": f"已选择设备 {run.device_serial or '自动发现'}，开始执行前置操作",
                    },
                )
                await events.record(
                    event_type="dispatch",
                    phase="executor",
                    action="start_executor",
                    parameters={"task_type": task.task_type.value},
                    result={"ok": True},
                )

                from app.models.apk import Apk
                from app.services.mobile_special.preflight import run_android_preflight

                apk = await db.get(Apk, run.apk_id) if run.apk_id is not None else None
                if apk is not None and apk.project_id != task.project_id:
                    raise RuntimeError("APK 资产不属于当前项目")
                if apk is not None and not run.app_package and apk.package_name:
                    run.app_package = apk.package_name
                    run.config_snapshot["app_package"] = apk.package_name
                preflight_result = await run_android_preflight(
                    serial=run.device_serial or "",
                    package=run.app_package,
                    config=run.config_snapshot,
                    apk_object_name=apk.object_name if apk is not None else None,
                )
                await _safe_publish_run_event(
                    run_id,
                    {
                        "type": "phase",
                        "run_id": run_id,
                        "phase": "preflight",
                        "progress": 25,
                        "current_step": "执行 Android 前置操作",
                        "device_serial": run.device_serial,
                        "device_status": "online",
                    },
                )
                await _safe_publish_run_event(
                    run_id,
                    {
                        "type": "log",
                        "run_id": run_id,
                        "level": "info",
                        "message": "前置操作完成，准备启动专项执行器",
                    },
                )
                await events.record(
                    event_type="phase",
                    phase="device_setup",
                    action="preflight",
                    parameters={"device_serial": run.device_serial, "app_package": run.app_package},
                    result={"ok": True, "actions": preflight_result.get("actions", [])},
                )
                if "launch_before" in (preflight_result.get("actions") or []):
                    # Executors also support auto_start; avoid launching the same app twice.
                    run.config_snapshot["auto_start"] = False
                    await db.commit()

                # 路由到对应 executor
                if task.task_type == TaskType.performance:
                    from app.worker.executors import run_mobile_special_perf

                    await run_mobile_special_perf(
                        db,
                        run,
                        cancel_check=lambda: is_cancel_requested(run_id, client=control_client),
                    )
                elif task.task_type == TaskType.stability:
                    from app.worker.executors import run_mobile_special_stability

                    await run_mobile_special_stability(
                        db,
                        run,
                        cancel_check=lambda: is_cancel_requested(run_id, client=control_client),
                    )
                elif task.task_type == TaskType.fluency:
                    from app.worker.executors import run_mobile_special_fluency

                    await run_mobile_special_fluency(
                        db,
                        run,
                        cancel_check=lambda: is_cancel_requested(run_id, client=control_client),
                    )
                else:
                    run.status = RunStatus.failed
                    run.summary_json = {"error_message": f"Unknown task_type: {task.task_type}"}
                    await db.commit()

            except Exception as e:
                logger.exception(f"Mobile special run {run_id} failed: {e}")
                run.status = RunStatus.failed
                run.finished_at = datetime.now(timezone.utc)
                run.summary_json = {"error_message": str(e)[:500]}
                await db.commit()
                await events.record(
                    event_type="run_error",
                    phase="dispatch",
                    action="exception",
                    level="error",
                    message=str(e)[:4000],
                    result={"ok": False, "error": str(e)[:500]},
                )
                await _safe_publish_run_event(
                    run_id,
                    {
                        "type": "log",
                        "run_id": run_id,
                        "level": "error",
                        "message": str(e)[:500],
                    },
                )
                await _safe_publish_run_event(
                    run_id,
                    {
                        "type": "completed",
                        "run_id": run_id,
                        "status": "failed",
                        "progress": 100,
                        "current_step": "执行失败",
                        "device_status": "online" if run.device_serial else "unknown",
                        "error": str(e)[:500],
                        "summary": run.summary_json,
                    },
                )
            finally:
                try:
                    from app.services.mobile_special_artifacts import capture_mobile_run_artifacts

                    await capture_mobile_run_artifacts(db, run, events)
                except Exception:
                    # 设备日志/截图属于辅助证据，不能覆盖专项执行本身的成功或失败状态。
                    logger.exception("Failed to capture final Android artifacts for mobile run %s", run_id)
                try:
                    from app.services.mobile_special.preflight import run_android_postflight

                    if run.device_serial:
                        await run_android_postflight(
                            serial=run.device_serial,
                            package=run.app_package,
                            config=run.config_snapshot or {},
                        )
                        await events.record(
                            event_type="phase",
                            phase="cleanup",
                            action="postflight",
                            result={"ok": True},
                        )
                except Exception:
                    logger.exception("Failed to apply Android postflight for mobile run %s", run_id)
                if lease_token:
                    try:
                        await release_device_lease(db, run.device_id, lease_token)
                        await db.commit()
                    except Exception:
                        logger.exception("Failed to release device lease for mobile run %s", run_id)

    try:
        run_async(_execute())
    finally:
        clear_cancel_request(run_id, client=control_client)
        control_client.close()


def _merge_run_config(task_config: dict[str, Any] | None, run_config: dict[str, Any] | None) -> dict[str, Any]:
    merged = dict(task_config or {})
    merged.update(run_config or {})
    return merged


def _resolve_run_device_id(run, task) -> int | None:
    config = run.config_snapshot or {}
    device_id = config.get("device_id")
    if isinstance(device_id, int):
        return device_id
    if run.device_id is not None:
        return run.device_id
    return task.device_id


def _resolve_run_app_package(run, task) -> str | None:
    config = run.config_snapshot or {}
    return config.get("app_package") or run.app_package or task.app_package


async def _get_device_serial(db, device_id: int | None) -> str | None:
    """根据设备 ID 获取 serial。"""
    if device_id is None:
        return None

    from app.models.device import Device

    device = await db.get(Device, device_id)
    if device:
        return device.serial
    return None


@celery_app.task(name="check_mobile_special_schedules")
def check_mobile_special_schedules():
    """每分钟检查启用的专项任务调度，到期则触发执行"""
    from app.core.database import AsyncSessionLocal
    from app.models.mobile_special import MobileSpecialTask, MobileSpecialRun, RunStatus, TriggerType, TaskType
    from sqlalchemy import select

    async def _check():
        async with AsyncSessionLocal() as db:
            now = datetime.now(timezone.utc)
            q = select(MobileSpecialTask).where(
                MobileSpecialTask.schedule_enabled == True,  # noqa: E712
                MobileSpecialTask.cron_expression.isnot(None),
                MobileSpecialTask.next_run_at.isnot(None),
                MobileSpecialTask.next_run_at <= now,
            )
            result = await db.execute(q)
            tasks = result.scalars().all()

            for task in tasks:
                # 创建 Run 记录
                run = MobileSpecialRun(
                    task_id=task.id,
                    task_type=task.task_type,
                    status=RunStatus.pending,
                    device_id=task.device_id,
                    app_package=task.app_package,
                    trigger_type=TriggerType.schedule,
                    triggered_by=None,
                    config_snapshot=task.config_json or {},
                )
                db.add(run)
                await db.commit()
                await db.refresh(run)

                # 更新下次调度时间
                try:
                    from croniter import croniter

                    cron = croniter(task.cron_expression, now)
                    task.next_run_at = cron.get_next(datetime)
                except Exception:
                    task.schedule_enabled = False
                task.last_run_at = now
                await db.commit()

                run_mobile_special_task.delay(run.id)
                logger.info(f"Schedule triggered task {task.id} -> run {run.id}")

    run_async(_check())


@celery_app.task(name="cleanup_stale_mobile_special_runs")
def cleanup_stale_mobile_special_runs():
    """定期清理超时的 pending/running 状态的 run"""
    from app.core.database import AsyncSessionLocal
    from app.models.mobile_special import MobileSpecialRun, RunStatus
    from sqlalchemy import update
    from datetime import datetime, timezone, timedelta

    async def _cleanup():
        async with AsyncSessionLocal() as db:
            threshold = datetime.now(timezone.utc) - timedelta(hours=2)
            stmt = (
                update(MobileSpecialRun)
                .where(
                    MobileSpecialRun.status.in_([RunStatus.pending, RunStatus.running]),
                    MobileSpecialRun.created_at < threshold,
                )
                .values(
                    status=RunStatus.stopped,
                    finished_at=datetime.now(timezone.utc),
                    summary_json={"error_message": "Run timeout, auto stopped"},
                )
            )
            await db.execute(stmt)
            await db.commit()

    run_async(_cleanup())


@celery_app.task(name="reclaim_expired_device_leases")
def reclaim_expired_device_leases_task():
    """回收执行器崩溃后遗留的设备租约。"""
    from app.core.database import AsyncSessionLocal
    from app.services.device_leases import reclaim_expired_device_leases

    async def _reclaim():
        async with AsyncSessionLocal() as db:
            count = await reclaim_expired_device_leases(db)
            await db.commit()
            logger.info("Reclaimed %d expired device lease(s)", count)

    run_async(_reclaim())
