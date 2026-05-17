"""
定期清理过期的 MinIO 文件（截图、报告等）与终态运行记录。
"""
import logging
from datetime import datetime, timedelta, timezone

from sqlalchemy import delete, select, update

from app.worker.celery_app import celery_app
from app.core.config import settings
from app.models.bootstrap import load_all_models
from app.services.storage_cleanup import (
    DEFAULT_CLEANUP_PREFIXES,
    execute_storage_cleanup,
    load_active_policies,
    preview_storage_cleanup,
)

logger = logging.getLogger(__name__)

_STALE_PENDING_ERROR = (
    "Execution exceeded pending timeout and was marked as error by the cleanup worker."
)


@celery_app.task(name="cleanup_expired_files")
def cleanup_expired_files():
    """按启用的 StoragePolicy 删除 MinIO 中过期且未被引用的对象。"""
    from app.core.database import sync_session_factory

    load_all_models()
    session = sync_session_factory()
    try:
        policies = load_active_policies(session)
        if not policies:
            policies_repr = [(prefix, settings.FILE_RETENTION_DAYS) for prefix in DEFAULT_CLEANUP_PREFIXES]
        else:
            policies_repr = [(p.prefix, p.retention_days) for p in policies]

        total_deleted = 0
        for prefix, retention_days in policies_repr:
            preview = preview_storage_cleanup(
                session,
                prefixes=[prefix],
                retention_days=retention_days,
            )
            if not preview.deletable_objects:
                continue
            result = execute_storage_cleanup(
                session,
                object_names=[item.object_name for item in preview.deletable_objects],
                repair_orphan_references=True,
            )
            total_deleted += result.deleted_count
            logger.info(
                "Cleanup prefix=%s retention=%d deleted=%d",
                prefix,
                retention_days,
                result.deleted_count,
            )

        logger.info("Cleanup finished: deleted %d expired files across %d policies", total_deleted, len(policies_repr))
        return {"deleted": total_deleted, "policies": len(policies_repr)}
    except Exception:
        session.rollback()
        logger.exception("Expired file cleanup task failed")
        return {"deleted": 0, "policies": 0}
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


def _collect_screenshot_objects(session, test_run_ids: list[int]) -> list[str]:
    from app.core.object_refs import extract_object_name
    from app.models.case import StepResult

    if not test_run_ids:
        return []
    rows = session.execute(
        select(StepResult.screenshot_url).where(
            StepResult.run_id.in_(test_run_ids),
            StepResult.screenshot_url.is_not(None),
        )
    ).all()
    objects: list[str] = []
    seen: set[str] = set()
    for (value,) in rows:
        object_name = extract_object_name(value)
        if not object_name or object_name in seen:
            continue
        seen.add(object_name)
        objects.append(object_name)
    return objects


def _collect_mobile_run_artifact_objects(session, run_ids: list[int]) -> list[str]:
    from app.core.object_refs import extract_object_name
    from app.models.mobile_special import MobileIncident, MobileRunArtifact

    if not run_ids:
        return []
    objects: list[str] = []
    seen: set[str] = set()
    for value, in session.execute(
        select(MobileRunArtifact.file_path).where(MobileRunArtifact.run_id.in_(run_ids))
    ).all():
        object_name = extract_object_name(value)
        if object_name and object_name not in seen:
            seen.add(object_name)
            objects.append(object_name)
    for value, in session.execute(
        select(MobileIncident.artifact_path).where(
            MobileIncident.run_id.in_(run_ids),
            MobileIncident.artifact_path.is_not(None),
        )
    ).all():
        object_name = extract_object_name(value)
        if object_name and object_name not in seen:
            seen.add(object_name)
            objects.append(object_name)
    return objects


def _delete_minio_objects(object_names: list[str]) -> int:
    from app.core import minio_client

    deleted = 0
    for name in object_names:
        try:
            minio_client.delete_file(name)
            deleted += 1
        except Exception:
            logger.exception("Failed to delete MinIO object during run cleanup: %s", name)
    return deleted


def _cleanup_test_runs(session, cutoff: datetime, batch_size: int) -> dict[str, int]:
    from app.models.case import RunStatus, TestRun

    terminal_statuses = (RunStatus.passed, RunStatus.failed, RunStatus.error, RunStatus.skipped)
    deleted_runs = 0
    deleted_objects = 0
    while True:
        rows = session.execute(
            select(TestRun.id)
            .where(TestRun.status.in_(terminal_statuses), TestRun.created_at < cutoff)
            .order_by(TestRun.id.asc())
            .limit(batch_size)
        ).all()
        ids = [row[0] for row in rows]
        if not ids:
            break
        object_names = _collect_screenshot_objects(session, ids)
        deleted_objects += _delete_minio_objects(object_names)
        session.execute(delete(TestRun).where(TestRun.id.in_(ids)))
        session.commit()
        deleted_runs += len(ids)
        if len(ids) < batch_size:
            break
    return {"runs": deleted_runs, "objects": deleted_objects}


def _cleanup_simple_runs(session, model, status_field, terminal_statuses, cutoff: datetime, batch_size: int) -> int:
    deleted = 0
    while True:
        rows = session.execute(
            select(model.id)
            .where(status_field.in_(terminal_statuses), model.created_at < cutoff)
            .order_by(model.id.asc())
            .limit(batch_size)
        ).all()
        ids = [row[0] for row in rows]
        if not ids:
            break
        session.execute(delete(model).where(model.id.in_(ids)))
        session.commit()
        deleted += len(ids)
        if len(ids) < batch_size:
            break
    return deleted


def _cleanup_mobile_special_runs(session, cutoff: datetime, batch_size: int) -> dict[str, int]:
    from app.models.mobile_special import MobileSpecialRun, RunStatus as MobileRunStatus

    terminal_statuses = (MobileRunStatus.completed, MobileRunStatus.failed, MobileRunStatus.stopped)
    deleted_runs = 0
    deleted_objects = 0
    while True:
        rows = session.execute(
            select(MobileSpecialRun.id)
            .where(MobileSpecialRun.status.in_(terminal_statuses), MobileSpecialRun.created_at < cutoff)
            .order_by(MobileSpecialRun.id.asc())
            .limit(batch_size)
        ).all()
        ids = [row[0] for row in rows]
        if not ids:
            break
        object_names = _collect_mobile_run_artifact_objects(session, ids)
        deleted_objects += _delete_minio_objects(object_names)
        session.execute(delete(MobileSpecialRun).where(MobileSpecialRun.id.in_(ids)))
        session.commit()
        deleted_runs += len(ids)
        if len(ids) < batch_size:
            break
    return {"runs": deleted_runs, "objects": deleted_objects}


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

    顺序：PlanRun → SuiteRun → TestRun → MobileSpecialRun。
    PlanRun/SuiteRun 仅删 DB 记录；TestRun 在删除前回收 StepResult 关联截图；
    MobileSpecialRun 在删除前回收 artifact_path 与 incident.artifact_path。
    """
    if not settings.RUN_CLEANUP_ENABLED:
        return {"enabled": False}

    from app.core.database import sync_session_factory
    from app.models.plan import PlanRun, PlanRunStatus
    from app.models.suite import SuiteRun, SuiteRunStatus

    load_all_models()
    session = sync_session_factory()
    try:
        cutoff = datetime.now(timezone.utc) - timedelta(days=settings.RUN_RETENTION_DAYS)
        batch_size = max(1, int(settings.RUN_CLEANUP_BATCH_SIZE))

        plan_deleted = _cleanup_simple_runs(
            session,
            PlanRun,
            PlanRun.status,
            (PlanRunStatus.passed, PlanRunStatus.failed, PlanRunStatus.error),
            cutoff,
            batch_size,
        )
        suite_deleted = _cleanup_simple_runs(
            session,
            SuiteRun,
            SuiteRun.status,
            (SuiteRunStatus.passed, SuiteRunStatus.failed, SuiteRunStatus.error),
            cutoff,
            batch_size,
        )
        test_stats = _cleanup_test_runs(session, cutoff, batch_size)
        mobile_stats = _cleanup_mobile_special_runs(session, cutoff, batch_size)

        summary = {
            "plan_runs": plan_deleted,
            "suite_runs": suite_deleted,
            "test_runs": test_stats["runs"],
            "mobile_runs": mobile_stats["runs"],
            "deleted_objects": test_stats["objects"] + mobile_stats["objects"],
            "retention_days": settings.RUN_RETENTION_DAYS,
        }
        if any(summary[k] for k in ("plan_runs", "suite_runs", "test_runs", "mobile_runs")):
            logger.info("Old run cleanup: %s", summary)
        else:
            logger.debug("Old run cleanup: nothing to delete (retention=%d days)", settings.RUN_RETENTION_DAYS)
        return summary
    except Exception:
        session.rollback()
        logger.exception("Old run cleanup task failed")
        return {"plan_runs": 0, "suite_runs": 0, "test_runs": 0, "mobile_runs": 0, "deleted_objects": 0}
    finally:
        session.close()
