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


def _terminal_performance_run_statuses():
    from app.models.performance import PerformanceRunStatus

    return (
        PerformanceRunStatus.success.value,
        PerformanceRunStatus.failed.value,
        PerformanceRunStatus.cancelled.value,
    )


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


def _collect_performance_run_objects(session: Session, run_ids: list[int]) -> list[str]:
    """Collect raw reports for root runs and their distributed shards."""
    from app.core.object_refs import extract_object_name
    from app.models.performance import PerformanceRun

    if not run_ids:
        return []
    rows = session.execute(
        select(PerformanceRun.raw_result_object_name).where(
            (PerformanceRun.id.in_(run_ids)) | (PerformanceRun.parent_run_id.in_(run_ids)),
            PerformanceRun.raw_result_object_name.is_not(None),
        )
    ).all()
    objects: list[str] = []
    seen: set[str] = set()
    for (value,) in rows:
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


def _count_id_statement(session: Session, ids_stmt) -> int:
    """Count the exact filtered id statement used by cleanup."""
    return int(session.execute(select(func.count()).select_from(ids_stmt.subquery())).scalar() or 0)


def _estimate_objects(
    session: Session,
    test_ids_stmt,
    mobile_ids_stmt,
    performance_ids_stmt,
    batch_size: int,
    test_count: int,
    mobile_count: int,
    performance_count: int,
) -> tuple[int, bool]:
    """Estimate attachment objects without loading every candidate run id."""
    test_sample = [row[0] for row in session.execute(test_ids_stmt.limit(batch_size)).all()]
    mobile_sample = [row[0] for row in session.execute(mobile_ids_stmt.limit(batch_size)).all()]
    performance_sample = [row[0] for row in session.execute(performance_ids_stmt.limit(batch_size)).all()]
    estimated_objects = (
        len(_collect_screenshot_objects(session, test_sample))
        + len(_collect_mobile_run_artifact_objects(session, mobile_sample))
        + len(_collect_performance_run_objects(session, performance_sample))
    )
    return estimated_objects, any(count > batch_size for count in (test_count, mobile_count, performance_count))


def preview_old_runs(
    session: Session,
    days: int,
    batch_size: int = 500,
    *,
    project_id: int | None = None,
    exclude_project_ids: list[int] | None = None,
) -> dict:
    """Preview the same scope that cleanup will delete.

    ``project_id`` is used for an override project. The global preview can pass
    ``exclude_project_ids`` so projects with their own retention policy are
    not counted twice or shown as eligible for the global cleanup pass.
    """
    cutoff = _cutoff(days)

    plan_ids_stmt = _plan_run_ids_stmt(cutoff, project_id, exclude_project_ids)
    suite_ids_stmt = _suite_run_ids_stmt(cutoff, project_id, exclude_project_ids)
    test_ids_stmt = _test_run_ids_stmt(cutoff, project_id, exclude_project_ids)
    mobile_ids_stmt = _mobile_run_ids_stmt(cutoff, project_id, exclude_project_ids)
    performance_ids_stmt = _performance_run_ids_stmt(cutoff, project_id, exclude_project_ids)

    plan_count = _count_id_statement(session, plan_ids_stmt)
    suite_count = _count_id_statement(session, suite_ids_stmt)
    test_count = _count_id_statement(session, test_ids_stmt)
    mobile_count = _count_id_statement(session, mobile_ids_stmt)
    performance_count = _count_id_statement(session, performance_ids_stmt)

    estimated_objects, estimated_objects_sampled = _estimate_objects(
        session,
        test_ids_stmt,
        mobile_ids_stmt,
        performance_ids_stmt,
        batch_size,
        test_count,
        mobile_count,
        performance_count,
    )

    return {
        "cutoff": cutoff,
        "retention_days": days,
        "plan_runs": plan_count,
        "suite_runs": suite_count,
        "test_runs": test_count,
        "mobile_runs": mobile_count,
        "performance_runs": performance_count,
        "estimated_objects": estimated_objects,
        "estimated_objects_sampled": estimated_objects_sampled,
    }


def _plan_run_ids_stmt(cutoff: datetime, project_id: int | None = None, exclude_project_ids: list[int] | None = None):
    from app.models.plan import PlanRun, TestPlan

    stmt = select(PlanRun.id).where(PlanRun.status.in_(_terminal_plan_run_statuses()), PlanRun.created_at < cutoff)
    if project_id is not None or exclude_project_ids:
        stmt = stmt.join(TestPlan, TestPlan.id == PlanRun.plan_id)
        if project_id is not None:
            stmt = stmt.where(TestPlan.project_id == project_id)
        elif exclude_project_ids:
            stmt = stmt.where(TestPlan.project_id.not_in(exclude_project_ids))
    return stmt.order_by(PlanRun.id.asc())


def _suite_run_ids_stmt(cutoff: datetime, project_id: int | None = None, exclude_project_ids: list[int] | None = None):
    from app.models.suite import SuiteRun, TestSuite

    stmt = select(SuiteRun.id).where(SuiteRun.status.in_(_terminal_suite_run_statuses()), SuiteRun.created_at < cutoff)
    if project_id is not None or exclude_project_ids:
        stmt = stmt.join(TestSuite, TestSuite.id == SuiteRun.suite_id)
        if project_id is not None:
            stmt = stmt.where(TestSuite.project_id == project_id)
        elif exclude_project_ids:
            stmt = stmt.where(TestSuite.project_id.not_in(exclude_project_ids))
    return stmt.order_by(SuiteRun.id.asc())


def _test_run_ids_stmt(cutoff: datetime, project_id: int | None = None, exclude_project_ids: list[int] | None = None):
    from app.models.case import TestCase, TestRun
    from app.models.project import Module

    stmt = select(TestRun.id).where(TestRun.status.in_(_terminal_test_run_statuses()), TestRun.created_at < cutoff)
    if project_id is not None or exclude_project_ids:
        stmt = stmt.join(TestCase, TestCase.id == TestRun.case_id).join(Module, Module.id == TestCase.module_id)
        if project_id is not None:
            stmt = stmt.where(Module.project_id == project_id)
        elif exclude_project_ids:
            stmt = stmt.where(Module.project_id.not_in(exclude_project_ids))
    return stmt.order_by(TestRun.id.asc())


def _mobile_run_ids_stmt(cutoff: datetime, project_id: int | None = None, exclude_project_ids: list[int] | None = None):
    from app.models.mobile_special import MobileSpecialRun, MobileSpecialTask

    stmt = select(MobileSpecialRun.id).where(
        MobileSpecialRun.status.in_(_terminal_mobile_run_statuses()), MobileSpecialRun.created_at < cutoff
    )
    if project_id is not None or exclude_project_ids:
        stmt = stmt.join(MobileSpecialTask, MobileSpecialTask.id == MobileSpecialRun.task_id)
        if project_id is not None:
            stmt = stmt.where(MobileSpecialTask.project_id == project_id)
        elif exclude_project_ids:
            stmt = stmt.where(MobileSpecialTask.project_id.not_in(exclude_project_ids))
    return stmt.order_by(MobileSpecialRun.id.asc())


def _performance_run_ids_stmt(
    cutoff: datetime,
    project_id: int | None = None,
    exclude_project_ids: list[int] | None = None,
):
    """Select terminal root performance runs; deleting a root cascades its shards and samples."""
    from app.models.performance import PerformanceRun

    stmt = select(PerformanceRun.id).where(
        PerformanceRun.status.in_(_terminal_performance_run_statuses()),
        PerformanceRun.created_at < cutoff,
        PerformanceRun.parent_run_id.is_(None),
    )
    if project_id is not None:
        stmt = stmt.where(PerformanceRun.project_id == project_id)
    elif exclude_project_ids:
        stmt = stmt.where(PerformanceRun.project_id.not_in(exclude_project_ids))
    return stmt.order_by(PerformanceRun.id.asc())


def _batched_delete_runs(session: Session, model, ids_stmt, batch_size: int, collect_objects=None) -> tuple[int, int]:
    """按批删除 ids_stmt 命中的运行记录；collect_objects 提供时先清理关联 MinIO 对象。"""
    deleted_runs = 0
    deleted_objects = 0
    while True:
        rows = session.execute(ids_stmt.limit(batch_size)).all()
        ids = [row[0] for row in rows]
        if not ids:
            break
        object_names = collect_objects(session, ids) if collect_objects is not None else []
        # 先提交数据库删除，再删除 MinIO 对象。提交失败时保留对象，避免出现
        # 运行记录仍存在但其截图/附件已经不可恢复的状态；对象删除失败只会
        # 留下可由存储治理任务发现的孤儿对象。
        session.execute(delete(model).where(model.id.in_(ids)))
        session.commit()
        deleted_runs += len(ids)
        if object_names:
            deleted_objects += _delete_minio_objects(object_names)
        if len(ids) < batch_size:
            break
    return deleted_runs, deleted_objects


def _cleanup_scope(
    session: Session,
    cutoff: datetime,
    batch_size: int,
    *,
    project_id: int | None = None,
    exclude_project_ids: list[int] | None = None,
) -> dict[str, int]:
    """清理一个范围（单项目 / 全局排除 override 项目）内的五类终态运行。"""
    from app.models.case import TestRun
    from app.models.mobile_special import MobileSpecialRun
    from app.models.plan import PlanRun
    from app.models.performance import PerformanceRun
    from app.models.suite import SuiteRun

    plan_ids_stmt = _plan_run_ids_stmt(cutoff, project_id, exclude_project_ids)
    suite_ids_stmt = _suite_run_ids_stmt(cutoff, project_id, exclude_project_ids)
    test_ids_stmt = _test_run_ids_stmt(cutoff, project_id, exclude_project_ids)
    mobile_ids_stmt = _mobile_run_ids_stmt(cutoff, project_id, exclude_project_ids)
    performance_ids_stmt = _performance_run_ids_stmt(cutoff, project_id, exclude_project_ids)

    plan_runs, _ = _batched_delete_runs(session, PlanRun, plan_ids_stmt, batch_size)
    suite_runs, _ = _batched_delete_runs(session, SuiteRun, suite_ids_stmt, batch_size)
    test_runs, test_objects = _batched_delete_runs(
        session, TestRun, test_ids_stmt, batch_size, collect_objects=_collect_screenshot_objects
    )
    mobile_runs, mobile_objects = _batched_delete_runs(
        session,
        MobileSpecialRun,
        mobile_ids_stmt,
        batch_size,
        collect_objects=_collect_mobile_run_artifact_objects,
    )
    performance_runs, performance_objects = _batched_delete_runs(
        session,
        PerformanceRun,
        performance_ids_stmt,
        batch_size,
        collect_objects=_collect_performance_run_objects,
    )
    return {
        "plan_runs": plan_runs,
        "suite_runs": suite_runs,
        "test_runs": test_runs,
        "mobile_runs": mobile_runs,
        "performance_runs": performance_runs,
        "deleted_objects": test_objects + mobile_objects + performance_objects,
    }


def execute_old_runs_cleanup(session: Session, days: int, batch_size: int = 500) -> dict:
    """真实清理：override 项目各按其保留天数清理，其余按全局天数清理（排除 override 项目）。"""
    batch_size = max(1, int(batch_size))

    overrides = list_projects_with_retention_override(session)
    override_ids = [pid for pid, _, _ in overrides]

    totals = {
        "plan_runs": 0,
        "suite_runs": 0,
        "test_runs": 0,
        "mobile_runs": 0,
        "performance_runs": 0,
        "deleted_objects": 0,
    }
    per_project: list[dict] = []
    for pid, name, project_days in overrides:
        stats = _cleanup_scope(session, _cutoff(project_days), batch_size, project_id=pid)
        per_project.append({"project_id": pid, "project_name": name, "retention_days": project_days, **stats})
        for key in totals:
            totals[key] += stats.get(key, 0)

    global_stats = _cleanup_scope(session, _cutoff(days), batch_size, exclude_project_ids=override_ids or None)
    for key in totals:
        totals[key] += global_stats.get(key, 0)

    return {
        "cutoff": _cutoff(days),
        "retention_days": days,
        **totals,
        "projects": per_project,
    }


# ============================================================================
# 项目维度保留天数（override 项目按其天数清理/预览，全局兜底排除 override 项目）
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
    from app.models.case import TestCase, TestRun
    from app.models.mobile_special import MobileSpecialRun, MobileSpecialTask
    from app.models.plan import PlanRun, TestPlan
    from app.models.performance import PerformanceRun
    from app.models.project import Module
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
        test_count = int(
            session.execute(
                select(func.count(TestRun.id))
                .join(TestCase, TestCase.id == TestRun.case_id)
                .join(Module, Module.id == TestCase.module_id)
                .where(
                    TestRun.status.in_(_terminal_test_run_statuses()),
                    TestRun.created_at < cutoff,
                    Module.project_id == pid,
                )
            ).scalar()
            or 0
        )
        mobile_count = int(
            session.execute(
                select(func.count(MobileSpecialRun.id))
                .join(MobileSpecialTask, MobileSpecialTask.id == MobileSpecialRun.task_id)
                .where(
                    MobileSpecialRun.status.in_(_terminal_mobile_run_statuses()),
                    MobileSpecialRun.created_at < cutoff,
                    MobileSpecialTask.project_id == pid,
                )
            ).scalar()
            or 0
        )
        performance_count = int(
            session.execute(
                select(func.count(PerformanceRun.id)).where(
                    PerformanceRun.status.in_(_terminal_performance_run_statuses()),
                    PerformanceRun.created_at < cutoff,
                    PerformanceRun.parent_run_id.is_(None),
                    PerformanceRun.project_id == pid,
                )
            ).scalar()
            or 0
        )
        estimated_objects, estimated_objects_sampled = _estimate_objects(
            session,
            _test_run_ids_stmt(cutoff, project_id=pid),
            _mobile_run_ids_stmt(cutoff, project_id=pid),
            _performance_run_ids_stmt(cutoff, project_id=pid),
            batch_size,
            test_count,
            mobile_count,
            performance_count,
        )
        project_previews.append(
            {
                "project_id": pid,
                "project_name": name,
                "retention_days": days,
                "plan_runs": plan_count,
                "suite_runs": suite_count,
                "test_runs": test_count,
                "mobile_runs": mobile_count,
                "performance_runs": performance_count,
                "estimated_objects": estimated_objects,
                "estimated_objects_sampled": estimated_objects_sampled,
            }
        )

    global_preview = preview_old_runs(
        session,
        global_days,
        batch_size,
        exclude_project_ids=[pid for pid, _, _ in overrides] or None,
    )
    return {
        "global": {
            "retention_days": global_preview["retention_days"],
            "plan_runs": global_preview["plan_runs"],
            "suite_runs": global_preview["suite_runs"],
            "test_runs": global_preview["test_runs"],
            "mobile_runs": global_preview["mobile_runs"],
            "performance_runs": global_preview.get("performance_runs", 0),
            "estimated_objects": global_preview["estimated_objects"],
            "estimated_objects_sampled": global_preview["estimated_objects_sampled"],
        },
        "projects": project_previews,
    }
