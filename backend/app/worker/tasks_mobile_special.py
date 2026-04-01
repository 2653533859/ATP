"""Celery tasks for mobile special testing domain."""
from datetime import datetime, timezone
from typing import Any

from app.worker.celery_app import celery_app
from app.worker.async_runner import run_async
from app.models.bootstrap import load_all_models
from app.core.redis_client import publish_run_event
import logging

logger = logging.getLogger(__name__)

load_all_models()


async def _safe_publish_run_event(run_id: int, payload: dict) -> None:
    try:
        await publish_run_event(run_id, payload)
    except Exception:
        logger.exception(f"Failed to publish event for run {run_id}")


@celery_app.task(bind=True, name="run_mobile_special_task")
def run_mobile_special_task(self, run_id: int):
    """统一执行入口，根据 task_type 路由到对应 executor"""
    from app.core.database import AsyncSessionLocal
    from app.models.mobile_special import MobileSpecialRun, MobileSpecialTask, RunStatus, TaskType

    async def _execute():
        async with AsyncSessionLocal() as db:
            run = await db.get(MobileSpecialRun, run_id)
            if not run:
                logger.error(f"MobileSpecialRun {run_id} not found")
                return

            task = await db.get(MobileSpecialTask, run.task_id)
            if not task:
                run.status = RunStatus.failed
                run.summary_json = {"error_message": "Task not found"}
                await db.commit()
                return

            run.config_snapshot = _merge_run_config(task.config_json, run.config_snapshot)
            run.task_type = task.task_type
            run.device_id = _resolve_run_device_id(run, task)
            run.app_package = _resolve_run_app_package(run, task)
            run.device_serial = (
                run.config_snapshot.get("device_serial")
                or await _get_device_serial(db, run.device_id)
            )
            if run.device_serial:
                run.config_snapshot["device_serial"] = run.device_serial
            await db.commit()

            try:
                await _safe_publish_run_event(run_id, {
                    "type": "run_status", "run_id": run_id, "status": "running"
                })

                # 路由到对应 executor
                if task.task_type == TaskType.performance:
                    from app.worker.executors import run_mobile_special_perf
                    await run_mobile_special_perf(db, run)
                elif task.task_type == TaskType.stability:
                    from app.worker.executors import run_mobile_special_stability
                    await run_mobile_special_stability(db, run)
                elif task.task_type == TaskType.fluency:
                    from app.worker.executors import run_mobile_special_fluency
                    await run_mobile_special_fluency(db, run)
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
                await _safe_publish_run_event(run_id, {
                    "type": "completed", "run_id": run_id, "status": "failed",
                })

    run_async(_execute())

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
