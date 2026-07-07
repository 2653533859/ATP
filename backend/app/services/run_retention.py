"""运行记录归档清理 — 抽离 service，供 Celery 周期任务和 admin API 共用。"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone

from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)


def _cutoff(days: int) -> datetime:
    return datetime.now(timezone.utc) - timedelta(days=days)


def _terminal_test_run_statuses():
    from app.models.case import RunStatus

    return (RunStatus.passed, RunStatus.failed, RunStatus.error, RunStatus.skipped)


def _terminal_plan_run_statuses():
    from app.models.plan import PlanRunStatus

    return (PlanRunStatus.passed, PlanRunStatus.failed, PlanRunStatus.error)


def _terminal_suite_run_statuses():
    from app.models.suite import SuiteRunStatus

    return (SuiteRunStatus.passed, SuiteRunStatus.failed, SuiteRunStatus.error)


def _terminal_mobile_run_statuses():
    from app.models.mobile_special import RunStatus as MobileRunStatus

    return (MobileRunStatus.completed, MobileRunStatus.failed, MobileRunStatus.stopped)


def _collect_screenshot_objects(session: Session, test_run_ids: list[int]) -> list[str]:
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


def _collect_mobile_run_artifact_objects(session: Session, run_ids: list[int]) -> list[str]:
    from app.core.object_refs import extract_object_name
    from app.models.mobile_special import MobileIncident, MobileRunArtifact

    if not run_ids:
        return []
    objects: list[str] = []
    seen: set[str] = set()
    for (value,) in session.execute(
        select(MobileRunArtifact.file_path).where(MobileRunArtifact.run_id.in_(run_ids))
    ).all():
        object_name = extract_object_name(value)
        if object_name and object_name not in seen:
            seen.add(object_name)
            objects.append(object_name)
    for (value,) in session.execute(
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


def _count_runs(session: Session, model, status_field, statuses, cutoff: datetime) -> int:
    stmt = select(func.count(model.id)).where(status_field.in_(statuses), model.created_at < cutoff)
    return int(session.execute(stmt).scalar() or 0)


def preview_old_runs(session: Session, days: int, batch_size: int = 500) -> dict:
    from app.models.case import TestRun
    from app.models.mobile_special import MobileSpecialRun
    from app.models.plan import PlanRun
    from app.models.suite import SuiteRun

    cutoff = _cutoff(days)

    plan_count = _count_runs(session, PlanRun, PlanRun.status, _terminal_plan_run_statuses(), cutoff)
    suite_count = _count_runs(session, SuiteRun, SuiteRun.status, _terminal_suite_run_statuses(), cutoff)
    test_count = _count_runs(session, TestRun, TestRun.status, _terminal_test_run_statuses(), cutoff)
    mobile_count = _count_runs(
        session, MobileSpecialRun, MobileSpecialRun.status, _terminal_mobile_run_statuses(), cutoff
    )

    test_sample = [
        row[0]
        for row in session.execute(
            select(TestRun.id)
            .where(TestRun.status.in_(_terminal_test_run_statuses()), TestRun.created_at < cutoff)
            .order_by(TestRun.id.asc())
            .limit(batch_size)
        ).all()
    ]
    mobile_sample = [
        row[0]
        for row in session.execute(
            select(MobileSpecialRun.id)
            .where(
                MobileSpecialRun.status.in_(_terminal_mobile_run_statuses()),
                MobileSpecialRun.created_at < cutoff,
            )
            .order_by(MobileSpecialRun.id.asc())
            .limit(batch_size)
        ).all()
    ]
    estimated_objects = len(_collect_screenshot_objects(session, test_sample)) + len(
        _collect_mobile_run_artifact_objects(session, mobile_sample)
    )

    return {
        "cutoff": cutoff,
        "retention_days": days,
        "plan_runs": plan_count,
        "suite_runs": suite_count,
        "test_runs": test_count,
        "mobile_runs": mobile_count,
        "estimated_objects": estimated_objects,
    }


def _cleanup_test_runs(session: Session, cutoff: datetime, batch_size: int) -> dict[str, int]:
    from app.models.case import TestRun

    terminal_statuses = _terminal_test_run_statuses()
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


def _cleanup_simple_runs(
    session: Session, model, status_field, terminal_statuses, cutoff: datetime, batch_size: int
) -> int:
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


def _cleanup_mobile_special_runs(session: Session, cutoff: datetime, batch_size: int) -> dict[str, int]:
    from app.models.mobile_special import MobileSpecialRun

    terminal_statuses = _terminal_mobile_run_statuses()
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


def execute_old_runs_cleanup(session: Session, days: int, batch_size: int = 500) -> dict:
    from app.models.plan import PlanRun
    from app.models.suite import SuiteRun

    cutoff = _cutoff(days)
    batch_size = max(1, int(batch_size))

    plan_deleted = _cleanup_simple_runs(
        session, PlanRun, PlanRun.status, _terminal_plan_run_statuses(), cutoff, batch_size
    )
    suite_deleted = _cleanup_simple_runs(
        session, SuiteRun, SuiteRun.status, _terminal_suite_run_statuses(), cutoff, batch_size
    )
    test_stats = _cleanup_test_runs(session, cutoff, batch_size)
    mobile_stats = _cleanup_mobile_special_runs(session, cutoff, batch_size)

    return {
        "cutoff": cutoff,
        "retention_days": days,
        "plan_runs": plan_deleted,
        "suite_runs": suite_deleted,
        "test_runs": test_stats["runs"],
        "mobile_runs": mobile_stats["runs"],
        "deleted_objects": test_stats["objects"] + mobile_stats["objects"],
    }


# ============================================================================
# P1.4 项目维度保留天数（MVP：解析 + 按项目预览；清理任务仍按全局）
# ============================================================================


def resolve_project_retention(session: Session, project_id: int, global_days: int) -> int:
    """返回项目实际生效的保留天数：project.run_retention_days_override 优先于全局。"""
    from app.models.project import Project

    override = session.execute(select(Project.run_retention_days_override).where(Project.id == project_id)).scalar()
    if override is not None and override > 0:
        return int(override)
    return int(global_days)


def list_projects_with_retention_override(session: Session) -> list[tuple[int, str, int]]:
    """列出所有设置了 retention override 的项目：(project_id, project_name, days)。"""
    from app.models.project import Project

    rows = session.execute(
        select(Project.id, Project.name, Project.run_retention_days_override)
        .where(Project.run_retention_days_override.is_not(None))
        .order_by(Project.id.asc())
    ).all()
    return [(int(pid), str(name), int(days)) for pid, name, days in rows if days and days > 0]


def preview_old_runs_by_project(session: Session, global_days: int, batch_size: int = 500) -> dict:
    """按项目维度返回预览：每个项目用其生效 days 计算（override > global），加全局兜底估算。

    返回结构：
    {
        "global": {"retention_days": N, "plan_runs": x, "suite_runs": y, ...},
        "projects": [
            {"project_id": 1, "project_name": "x", "retention_days": 30, "plan_runs": ...},
            ...
        ],
    }
    """
    from app.models.plan import PlanRun, TestPlan
    from app.models.suite import SuiteRun, TestSuite

    overrides = list_projects_with_retention_override(session)

    project_previews: list[dict] = []
    for pid, name, days in overrides:
        cutoff = _cutoff(days)
        # PlanRun / SuiteRun 通过 plan_id / suite_id 关联项目
        plan_count = int(
            session.execute(
                select(func.count(PlanRun.id))
                .join(TestPlan, TestPlan.id == PlanRun.plan_id)
                .where(
                    PlanRun.status.in_(_terminal_plan_run_statuses()),
                    PlanRun.created_at < cutoff,
                    TestPlan.project_id == pid,
                )
            ).scalar()
            or 0
        )
        suite_count = int(
            session.execute(
                select(func.count(SuiteRun.id))
                .join(TestSuite, TestSuite.id == SuiteRun.suite_id)
                .where(
                    SuiteRun.status.in_(_terminal_suite_run_statuses()),
                    SuiteRun.created_at < cutoff,
                    TestSuite.project_id == pid,
                )
            ).scalar()
            or 0
        )
        project_previews.append(
            {
                "project_id": pid,
                "project_name": name,
                "retention_days": days,
                "plan_runs": plan_count,
                "suite_runs": suite_count,
                # TestRun / MobileSpecialRun 跨多级 join 较重，留待真正按项目清理时再补
                "note": "test_runs / mobile_runs 预览暂按全局统计，按项目过滤待后续迭代",
            }
        )

    global_preview = preview_old_runs(session, global_days, batch_size)
    return {
        "global": {
            "retention_days": global_preview["retention_days"],
            "plan_runs": global_preview["plan_runs"],
            "suite_runs": global_preview["suite_runs"],
            "test_runs": global_preview["test_runs"],
            "mobile_runs": global_preview["mobile_runs"],
            "estimated_objects": global_preview["estimated_objects"],
        },
        "projects": project_previews,
    }
