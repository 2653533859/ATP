from celery import Celery
from app.core.config import settings

celery_app = Celery(
    "atp",
    broker=settings.CELERY_BROKER_URL,
    backend=settings.CELERY_RESULT_BACKEND,
    include=["app.worker.tasks", "app.worker.tasks_device"],
)

celery_app.conf.update(
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    timezone="Asia/Shanghai",
    enable_utc=True,
    task_track_started=True,
    worker_prefetch_multiplier=1,
    beat_schedule={
        "scan-adb-devices": {
            "task": "scan_adb_devices",
            "schedule": settings.ADB_SCAN_INTERVAL,
        },
        "check-cron-plans": {
            "task": "check_cron_plans",
            "schedule": 60.0,
        },
    },
)
