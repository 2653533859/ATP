from celery import Celery
from celery.signals import worker_process_init, worker_process_shutdown

from app.core.config import settings

celery_app = Celery(
    "atp",
    broker=settings.CELERY_BROKER_URL,
    backend=settings.CELERY_RESULT_BACKEND,
    include=["app.worker.tasks", "app.worker.tasks_device", "app.worker.tasks_cleanup", "app.worker.tasks_mobile_special"],
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
