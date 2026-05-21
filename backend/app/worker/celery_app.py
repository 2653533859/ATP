from celery import Celery
from celery.schedules import crontab
from celery.signals import (
    task_failure,
    task_revoked,
    worker_process_init,
    worker_process_shutdown,
)

from app.core.config import settings
from app.worker.timeout_alerts import on_task_failure, on_task_revoked

celery_app = Celery(
    "atp",
    broker=settings.CELERY_BROKER_URL,
    backend=settings.CELERY_RESULT_BACKEND,
    include=[
        "app.worker.tasks",
        "app.worker.tasks_device",
        "app.worker.tasks_cleanup",
        "app.worker.tasks_mobile_special",
        "app.worker.tasks_db_backup",
    ],
)

celery_app.conf.update(
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    timezone="Asia/Shanghai",
    enable_utc=True,
    task_track_started=True,
    worker_prefetch_multiplier=1,
    # 资源隔离: 单任务最大执行时间 30 分钟，软限制 25 分钟
    task_time_limit=1800,
    task_soft_time_limit=1500,
    # 每个 worker 处理 50 个任务后回收，防止内存泄漏
    worker_max_tasks_per_child=50,
    beat_schedule={
        "scan-adb-devices": {
            "task": "scan_adb_devices",
            "schedule": settings.ADB_SCAN_INTERVAL,
        },
        "check-cron-plans": {
            "task": "check_cron_plans",
            "schedule": 60.0,
        },
        "cleanup-expired-files": {
            "task": "cleanup_expired_files",
            "schedule": 86400.0,  # 每 24 小时执行一次
        },
        "cleanup-old-completed-runs": {
            "task": "cleanup_old_completed_runs",
            "schedule": 86400.0,  # 每 24 小时执行一次
        },
        "check-storage-usage": {
            "task": "check_storage_usage",
            "schedule": 3600.0,  # 每小时一次
        },
        "cleanup-stale-pending-runs": {
            "task": "cleanup_stale_pending_runs",
            "schedule": settings.STALE_PENDING_CLEANUP_INTERVAL_SECONDS,
        },
        "check-mobile-special-schedules": {
            "task": "check_mobile_special_schedules",
            "schedule": 60.0,
        },
        "cleanup-stale-mobile-special-runs": {
            "task": "cleanup_stale_mobile_special_runs",
            "schedule": 1800.0,
        },
        "backup-postgres-daily": {
            "task": "backup_postgres_daily",
            # 每日凌晨 03:17（错峰，避免与其他备份扎堆）
            "schedule": crontab(hour=3, minute=17),
        },
        "backup-postgres-weekly": {
            "task": "backup_postgres_weekly",
            # 每周一凌晨 04:33
            "schedule": crontab(hour=4, minute=33, day_of_week=1),
        },
    },
)


# OTel 必须在每个 worker 子进程内初始化（pre-fork 模型决定）。
@worker_process_init.connect
def _init_otel(**_kwargs):
    from opentelemetry.instrumentation.celery import CeleryInstrumentor

    from app.core.otel import init_tracer

    init_tracer("atp-worker")
    CeleryInstrumentor().instrument()


@worker_process_shutdown.connect
def _shutdown_otel(**_kwargs):
    from app.core.otel import shutdown_tracer

    shutdown_tracer()


# Soft / Hard 超时告警桥接到独立 handler 模块（便于单测）
@task_failure.connect
def _on_task_failure(sender=None, task_id=None, exception=None, **_):
    sender_name = getattr(sender, "name", str(sender))
    on_task_failure(sender_name, task_id, exception)


@task_revoked.connect
def _on_task_revoked(sender=None, request=None, terminated=False, signum=None, expired=False, **_):
    sender_name = getattr(sender, "name", str(sender))
    task_id = getattr(request, "id", None) if request is not None else None
    on_task_revoked(sender_name, task_id, terminated, signum, expired)
