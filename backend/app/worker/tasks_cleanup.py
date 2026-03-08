"""
定期清理过期的 MinIO 文件（截图、报告等）
"""
import logging
from datetime import datetime, timedelta, timezone

from app.worker.celery_app import celery_app
from app.core.config import settings
from app.core import minio_client

logger = logging.getLogger(__name__)

# 需要清理的对象前缀
_CLEANUP_PREFIXES = ("screenshots/", "reports/", "apks/")


@celery_app.task(name="cleanup_expired_files")
def cleanup_expired_files():
    """删除 MinIO 中超过保留期限的文件"""
    cutoff = datetime.now(timezone.utc) - timedelta(days=settings.FILE_RETENTION_DAYS)
    deleted = 0

    for prefix in _CLEANUP_PREFIXES:
        try:
            objects = minio_client.list_objects(prefix=prefix)
        except Exception as e:
            logger.error("Failed to list objects with prefix %s: %s", prefix, e)
            continue

        for obj in objects:
            if obj.last_modified and obj.last_modified < cutoff:
                try:
                    minio_client.delete_file(obj.object_name)
                    deleted += 1
                except Exception as e:
                    logger.error("Failed to delete %s: %s", obj.object_name, e)

    logger.info("Cleanup finished: deleted %d expired files (retention=%d days)", deleted, settings.FILE_RETENTION_DAYS)
    return {"deleted": deleted}
