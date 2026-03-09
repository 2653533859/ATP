"""
定期清理过期的 MinIO 文件（截图、报告等）
"""
import logging
from datetime import datetime, timedelta, timezone

from sqlalchemy import update

from app.worker.celery_app import celery_app
from app.core.config import settings
from app.core import minio_client
from app.models.bootstrap import load_all_models

logger = logging.getLogger(__name__)

# 需要清理的对象前缀
_CLEANUP_PREFIXES = ("screenshots/", "reports/", "apks/")
_STALE_PENDING_ERROR = (
    "Execution exceeded pending timeout and was marked as error by the cleanup worker."
)


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


def _cleanup_stale_pending_with_session(session, now: datetime) -> dict[str, int]:
    from app.models.case import TestRun, RunStatus
    from app.models.suite import SuiteRun, SuiteRunStatus
    from app.models.plan import PlanRun, PlanRunStatus

    cutoff = now - timedelta(minutes=settings.STALE_PENDING_TIMEOUT_MINUTES)
    counts: dict[str, int] = {"test_runs": 0, "suite_runs": 0, "plan_runs": 0}

    statements = (
        (
            "test_runs",
            update(TestRun)
            .where(TestRun.status == RunStatus.pending, TestRun.created_at < cutoff)
            .values(status=RunStatus.error, error_message=_STALE_PENDING_ERROR)
            .execution_options(synchronize_session=False),
        ),
        (
            "suite_runs",
            update(SuiteRun)
            .where(SuiteRun.status == SuiteRunStatus.pending, SuiteRun.created_at < cutoff)
            .values(status=SuiteRunStatus.error, error_message=_STALE_PENDING_ERROR)
            .execution_options(synchronize_session=False),
        ),
        (
            "plan_runs",
            update(PlanRun)
            .where(PlanRun.status == PlanRunStatus.pending, PlanRun.created_at < cutoff)
            .values(status=PlanRunStatus.error, error_message=_STALE_PENDING_ERROR)
            .execution_options(synchronize_session=False),
        ),
    )

    for key, stmt in statements:
        result = session.execute(stmt)
        counts[key] = result.rowcount or 0

    counts["total"] = sum(counts.values())
    return counts


@celery_app.task(name="cleanup_stale_pending_runs")
def cleanup_stale_pending_runs():
    """将超过阈值仍处于 pending 的执行记录标记为 error。"""
    if not settings.STALE_PENDING_CLEANUP_ENABLED:
        return {"test_runs": 0, "suite_runs": 0, "plan_runs": 0, "total": 0}

    from app.core.database import sync_session_factory

    load_all_models()
    session = sync_session_factory()
    try:
        counts = _cleanup_stale_pending_with_session(session, datetime.now(timezone.utc))
        session.commit()
        if counts["total"]:
            logger.warning(
                "Marked stale pending runs as error: test=%d suite=%d plan=%d timeout=%dmin",
                counts["test_runs"],
                counts["suite_runs"],
                counts["plan_runs"],
                settings.STALE_PENDING_TIMEOUT_MINUTES,
            )
        else:
            logger.debug(
                "No stale pending runs found (timeout=%dmin)",
                settings.STALE_PENDING_TIMEOUT_MINUTES,
            )
        return counts
    except Exception:
        session.rollback()
        logger.exception("Stale pending cleanup task failed")
        return {"test_runs": 0, "suite_runs": 0, "plan_runs": 0, "total": 0}
    finally:
        session.close()
