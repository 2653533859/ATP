"""
定期清理过期的 MinIO 文件（截图、报告等）与终态运行记录。
"""

import logging
from datetime import datetime, timedelta, timezone

from sqlalchemy import update

from app.worker.celery_app import celery_app
from app.core.config import settings
from app.models.bootstrap import load_all_models
from app.services.storage_cleanup import (
    DEFAULT_CLEANUP_PREFIXES,
    PolicyEntry,
    execute_storage_cleanup,
    load_active_policies,
    preview_storage_cleanup,
)
from app.services.run_retention import execute_old_runs_cleanup

logger = logging.getLogger(__name__)

_STALE_PENDING_ERROR = "Execution exceeded pending timeout and was marked as error by the cleanup worker."


@celery_app.task(name="cleanup_expired_files")
def cleanup_expired_files():
    """按启用的 StoragePolicy 删除 MinIO 中过期且未被引用的对象。

    每条 policy 独立预览/执行：retention_days 与 max_size_gb 取并集，由
    ``preview_storage_cleanup`` 统一计算淘汰对象集合。
    """
    from app.core.database import sync_session_factory

    load_all_models()
    session = sync_session_factory()
    try:
        policies = load_active_policies(session)
        if not policies:
            policies = [
                PolicyEntry(prefix=prefix, retention_days=settings.FILE_RETENTION_DAYS, max_size_gb=None)
                for prefix in DEFAULT_CLEANUP_PREFIXES
            ]

        total_deleted = 0
        total_size_evicted = 0
        for policy in policies:
            preview = preview_storage_cleanup(session, policies=[policy])
            if not preview.deletable_objects:
                continue
            result = execute_storage_cleanup(
                session,
                object_names=[item.object_name for item in preview.deletable_objects],
                repair_orphan_references=True,
            )
            total_deleted += result.deleted_count
            total_size_evicted += preview.size_evicted_count
            logger.info(
                "Cleanup prefix=%s retention=%d max_size_gb=%s deleted=%d size_evicted=%d",
                policy.prefix,
                policy.retention_days,
                policy.max_size_gb,
                result.deleted_count,
                preview.size_evicted_count,
            )

        logger.info(
            "Cleanup finished: deleted %d expired files (size-evicted %d) across %d policies",
            total_deleted,
            total_size_evicted,
            len(policies),
        )
        return {
            "deleted": total_deleted,
            "size_evicted": total_size_evicted,
            "policies": len(policies),
        }
    except Exception:
        session.rollback()
        logger.exception("Expired file cleanup task failed")
        return {"deleted": 0, "size_evicted": 0, "policies": 0}
    finally:
        session.close()


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


@celery_app.task(name="check_storage_usage")
def check_storage_usage():
    """检查 MinIO bucket 总大小，必要时写入/清除告警状态。"""
    if (settings.STORAGE_ALERT_SIZE_GB or 0) <= 0:
        return {"enabled": False}

    import asyncio

    from app.services.storage_alerts import check_and_record_alert

    load_all_models()
    try:
        result = asyncio.run(check_and_record_alert())
        return {"enabled": True, "alert": result}
    except Exception:
        logger.exception("Storage usage check failed")
        return {"enabled": True, "alert": None, "error": True}


@celery_app.task(name="cleanup_old_completed_runs")
def cleanup_old_completed_runs():
    """删除超过保留期的终态运行记录及其关联文件。

    实际清理逻辑抽到 ``app.services.run_retention``，供本任务与 admin API 共用。
    """
    if not settings.RUN_CLEANUP_ENABLED:
        return {"enabled": False}

    from app.core.database import sync_session_factory

    load_all_models()
    session = sync_session_factory()
    try:
        summary = execute_old_runs_cleanup(
            session,
            days=settings.RUN_RETENTION_DAYS,
            batch_size=settings.RUN_CLEANUP_BATCH_SIZE,
        )
        if any(summary[k] for k in ("plan_runs", "suite_runs", "test_runs", "mobile_runs")):
            logger.info("Old run cleanup: %s", summary)
        else:
            logger.debug(
                "Old run cleanup: nothing to delete (retention=%d days)",
                settings.RUN_RETENTION_DAYS,
            )
        return summary
    except Exception:
        session.rollback()
        logger.exception("Old run cleanup task failed")
        return {
            "plan_runs": 0,
            "suite_runs": 0,
            "test_runs": 0,
            "mobile_runs": 0,
            "deleted_objects": 0,
        }
    finally:
        session.close()
