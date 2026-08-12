from celery import Celery
from celery.schedules import crontab
from celery.signals import (
    task_failure,
    task_revoked,
    worker_ready,
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
        "app.worker.tasks_ios",
        "app.worker.tasks_db_backup",
        "app.worker.tasks_healing",
        "app.worker.tasks_performance",
    ],
)

celery_app.conf.update(
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    task_default_queue="default",
    task_create_missing_queues=True,
    task_routes={
        # 高频普通执行入口
        "run_test_case": {"queue": "default"},
        "run_test_suite": {"queue": "default"},
        "run_test_plan": {"queue": "default"},
        "check_cron_plans": {"queue": "default"},
        "check_performance_schedules": {"queue": "performance"},
        "heartbeat_performance_node": {"queue": "performance"},
        # Android 专项与设备扫描，通常受真机资源约束
        "run_mobile_special_task": {"queue": "mobile_special"},
        "reclaim_expired_ios_device_leases": {"queue": "ios"},
        "check_mobile_special_schedules": {"queue": "mobile_special"},
        "cleanup_stale_mobile_special_runs": {"queue": "mobile_special"},
        "reclaim_expired_device_leases": {"queue": "mobile_special"},
        "scan_adb_devices": {"queue": "mobile_special"},
        "heartbeat_android_worker": {"queue": "mobile_special"},
        # 外部 LLM 调用，便于独立限流与降级
        "diagnose_step_failure": {"queue": "ai"},
        "diagnose_run_failure": {"queue": "ai"},
        "aggregate_healing_feedback": {"queue": "ai"},
        # HTTP 压测任务，预留独立 worker 与资源配额
        "run_performance_test": {"queue": "performance"},
        # 清理、备份、告警等后台维护任务
        "cleanup_expired_files": {"queue": "maintenance"},
        "cleanup_stale_pending_runs": {"queue": "maintenance"},
        "cleanup_old_completed_runs": {"queue": "maintenance"},
        "check_storage_usage": {"queue": "maintenance"},
        "check_dashboard_alerts": {"queue": "maintenance"},
        "backup_postgres_daily": {"queue": "maintenance"},
        "backup_postgres_weekly": {"queue": "maintenance"},
    },
    timezone="Asia/Shanghai",
    enable_utc=True,
    task_track_started=True,
    worker_prefetch_multiplier=1,
    broker_transport_options={
        "socket_connect_timeout": settings.REDIS_CONNECT_TIMEOUT_SECONDS,
        "socket_timeout": settings.REDIS_CONNECT_TIMEOUT_SECONDS,
    },
    result_backend_transport_options={
        "socket_connect_timeout": settings.REDIS_CONNECT_TIMEOUT_SECONDS,
        "socket_timeout": settings.REDIS_CONNECT_TIMEOUT_SECONDS,
    },
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
        "check-performance-schedules": {
            "task": "check_performance_schedules",
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
        "check-dashboard-alerts": {
            "task": "check_dashboard_alerts",
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
        "reclaim-expired-ios-device-leases": {
            "task": "reclaim_expired_ios_device_leases",
            "schedule": 60.0,
        },
        "reclaim-expired-device-leases": {
            "task": "reclaim_expired_device_leases",
            "schedule": 60.0,
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
        "aggregate-healing-feedback": {
            "task": "aggregate_healing_feedback",
            # 每周一凌晨 04:17，供 prompt 示例库与反馈报表复用
            "schedule": crontab(hour=4, minute=17, day_of_week=1),
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


# Prometheus /metrics 端点：每个 worker 子进程尝试启动；首个成功绑定，其余 OSError 静默
# （多 worker 进程共享同一物理端口）。可通过 WORKER_METRICS_PORT=0 关闭。
@worker_process_init.connect
def _init_worker_metrics(**_kwargs):
    from app.core.metrics import start_worker_metrics_server

    start_worker_metrics_server(settings.WORKER_METRICS_PORT)


@worker_process_shutdown.connect
def _shutdown_otel(**_kwargs):
    from app.core.otel import shutdown_tracer

    shutdown_tracer()


@worker_ready.connect
def _schedule_performance_node_heartbeat(**_kwargs):
    """Start one self-rescheduling heartbeat chain for each explicitly configured worker."""
    if not settings.PERFORMANCE_NODE_ENABLED or not settings.PERFORMANCE_NODE_ID.strip():
        return
    from app.services.performance_node import worker_node_queue
    from app.worker.tasks_performance import heartbeat_performance_node

    heartbeat_performance_node.apply_async(queue=worker_node_queue())


@worker_ready.connect
def _schedule_android_worker_heartbeat(**_kwargs):
    """Start a TTL-backed registry heartbeat only for explicitly identified Android Workers."""
    if not settings.ANDROID_WORKER_ID.strip():
        return
    from app.worker.tasks_device import heartbeat_android_worker

    heartbeat_android_worker.apply_async(queue=settings.ANDROID_WORKER_QUEUE.strip() or "mobile_special")


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
