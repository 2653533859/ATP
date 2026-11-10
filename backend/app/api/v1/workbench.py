"""Workbench aggregation and unified task actions.

The workbench is intentionally a read/dispatch layer.  It does not introduce a
second execution engine or a second source of truth for run state: list data is
read from the existing run tables and actions delegate to the existing domain
endpoints, so their project-role and executor checks remain authoritative.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any, cast

from fastapi import APIRouter, Depends, Header, HTTPException, Query
from sqlalchemy import and_, false, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import assert_project_access, get_current_user
from app.core.database import get_db
from app.models.case import RunStatus, TestCase, TestRun
from app.models.device import Device, DeviceStatus
from app.models.mobile_special import MobileSpecialRun, MobileSpecialTask, RunStatus as MobileRunStatus
from app.models.performance import PerformanceRun, PerformanceRunStatus, PerformanceTest
from app.models.plan import PlanRun, PlanRunStatus, ScheduleType, TestPlan
from app.models.project import Module, Project
from app.models.suite import SuiteRun, SuiteRunStatus, TestSuite
from app.models.user import User, UserRole
from app.models.user_project import ProjectRole, UserProject
from app.models.workbench import WorkbenchArchivedTask, WorkbenchTodoSnooze
from app.schemas.case import FailureDiagnosisOut, RunTriggerRequest
from app.schemas.mobile_special import RunTriggerRequest as MobileRunTriggerRequest
from app.schemas.performance import PerformanceRunTrigger
from app.schemas.plan import PlanRunTrigger
from app.schemas.suite import SuiteRunTrigger
from app.schemas.workbench import (
    WorkbenchAction,
    WorkbenchBatchActionIn,
    WorkbenchBatchActionOut,
    WorkbenchOverviewOut,
    WorkbenchTaskActionOut,
    WorkbenchTaskArchiveIn,
    WorkbenchTaskArchiveOut,
    WorkbenchTaskItem,
    WorkbenchTaskPageOut,
    WorkbenchTaskRef,
    WorkbenchTaskType,
    WorkbenchTodoItem,
    WorkbenchTodoSnoozeIn,
    WorkbenchTodoSnoozeOut,
)
from app.services.execution_state import (
    EXECUTION_STATE_POLICIES,
    can_execute_action,
    decide_execution_action,
    execution_action_rejection_detail,
)
from app.services.execution_commands import (
    claim_execution_command,
    complete_execution_command,
    fail_execution_command,
    mark_execution_command_indeterminate,
    normalize_execution_command_id,
)
from app.services.project_scope import scope_to_visible_projects
from app.services.workbench_diagnosis import generate_workbench_failure_diagnosis

router = APIRouter(tags=["工作台"])

_TASK_TYPES = {"case", "suite", "plan", "android", "performance"}
_ACTIVE_STATUSES = set().union(*(policy.active for policy in EXECUTION_STATE_POLICIES.values()))
_FAILED_STATUSES = set().union(*(policy.failed for policy in EXECUTION_STATE_POLICIES.values()))
_STATUS_VALUES_BY_TYPE = {domain: policy.statuses for domain, policy in EXECUTION_STATE_POLICIES.items()}
StatusFilter = str | set[str] | None


def _enum_value(value: Any) -> str:
    return str(getattr(value, "value", value))


def _project_filter(stmt, project_column, user: User, project_id: int | None):
    return scope_to_visible_projects(stmt, project_column, user, project_id)


def _apply_status_filter(stmt, status_column, status_filter: StatusFilter):
    if status_filter is None:
        return stmt
    if isinstance(status_filter, (set, frozenset, list, tuple)):
        if not status_filter:
            return stmt.where(false())
        return stmt.where(status_column.in_(status_filter))
    return stmt.where(status_column == status_filter)


def _status_filter_for_type(status_filter: StatusFilter, task_type: str) -> StatusFilter:
    """Keep status literals valid for the enum used by a task domain.

    The workbench aggregates several tables, but their PostgreSQL enums are
    intentionally different.  Passing the union of all terminal statuses to
    every table makes PostgreSQL reject a query before it can return an empty
    result (for example, ``TestRun.status IN ('stopped')``).
    """

    if status_filter is None:
        return None
    allowed = _STATUS_VALUES_BY_TYPE[task_type]
    if isinstance(status_filter, (set, frozenset, list, tuple)):
        return {str(value) for value in status_filter if str(value) in allowed}
    return status_filter if status_filter in allowed else set()


def _apply_archived_filter(stmt: Any, run_id_column: Any, task_type: str, archived_filter: str | None) -> Any:
    if archived_filter == "exclude":
        archived_subq = select(WorkbenchArchivedTask.run_id).where(WorkbenchArchivedTask.task_type == task_type)
        return stmt.where(run_id_column.not_in(archived_subq))
    if archived_filter == "only":
        archived_subq = select(WorkbenchArchivedTask.run_id).where(WorkbenchArchivedTask.task_type == task_type)
        return stmt.where(run_id_column.in_(archived_subq))
    return stmt


def _task_item(
    *,
    task_type: WorkbenchTaskType,
    run_id: int,
    source_id: int,
    project_id: int | None,
    project_name: str | None,
    name: str,
    status_value: Any,
    created_at: datetime | None,
    started_at: datetime | None = None,
    finished_at: datetime | None = None,
    duration_ms: int | None = None,
    error_message: str | None = None,
    detail_path: str,
    metadata: dict | None = None,
) -> WorkbenchTaskItem:
    status = _enum_value(status_value)
    can_retry = can_execute_action(task_type, status, "retry")
    can_stop = can_execute_action(task_type, status, "stop")

    return WorkbenchTaskItem(
        id=f"{task_type}:{run_id}",
        task_type=task_type,
        run_id=run_id,
        source_id=source_id,
        project_id=project_id,
        project_name=project_name,
        name=name,
        status=status,
        created_at=created_at,
        started_at=started_at,
        finished_at=finished_at,
        duration_ms=duration_ms,
        error_message=error_message,
        detail_path=detail_path,
        can_retry=can_retry,
        can_stop=can_stop,
        metadata=metadata or {},
    )


async def _collect_case_tasks(
    db: AsyncSession,
    user: User,
    project_id: int | None,
    status_filter: StatusFilter,
    limit: int,
    archived_filter: str | None = None,
    exclude_run_ids: set[int] | None = None,
    only_run_ids: set[int] | None = None,
) -> tuple[list[WorkbenchTaskItem], bool]:
    if only_run_ids is not None and not only_run_ids:
        return [], False
    stmt = (
        select(TestRun, TestCase.name, Module.project_id, Project.name)
        .join(TestCase, TestRun.case_id == TestCase.id)
        .join(Module, TestCase.module_id == Module.id)
        .join(Project, Module.project_id == Project.id)
    )
    stmt = _project_filter(stmt, Module.project_id, user, project_id)
    stmt = _apply_status_filter(stmt, TestRun.status, status_filter)
    stmt = _apply_archived_filter(stmt, TestRun.id, "case", archived_filter)
    if exclude_run_ids:
        stmt = stmt.where(TestRun.id.not_in(exclude_run_ids))
    if only_run_ids is not None:
        stmt = stmt.where(TestRun.id.in_(only_run_ids))
    rows = (await db.execute(stmt.order_by(TestRun.created_at.desc(), TestRun.id.desc()).limit(limit + 1))).all()
    has_more = len(rows) > limit
    items = [
        _task_item(
            task_type="case",
            run_id=run.id,
            source_id=run.case_id,
            project_id=case_project_id,
            project_name=project_name,
            name=case_name,
            status_value=run.status,
            created_at=run.created_at,
            duration_ms=run.duration_ms,
            error_message=run.error_message,
            detail_path=f"/runs/{run.id}?project_id={case_project_id}",
            metadata={"case_id": run.case_id},
        )
        for run, case_name, case_project_id, project_name in rows[:limit]
    ]
    return items, has_more


async def _collect_suite_tasks(
    db: AsyncSession,
    user: User,
    project_id: int | None,
    status_filter: StatusFilter,
    limit: int,
    archived_filter: str | None = None,
    exclude_run_ids: set[int] | None = None,
    only_run_ids: set[int] | None = None,
) -> tuple[list[WorkbenchTaskItem], bool]:
    if only_run_ids is not None and not only_run_ids:
        return [], False
    stmt = (
        select(SuiteRun, TestSuite.name, TestSuite.project_id, Project.name)
        .join(TestSuite, SuiteRun.suite_id == TestSuite.id)
        .join(Project, TestSuite.project_id == Project.id)
    )
    stmt = _project_filter(stmt, TestSuite.project_id, user, project_id)
    stmt = _apply_status_filter(stmt, SuiteRun.status, status_filter)
    stmt = _apply_archived_filter(stmt, SuiteRun.id, "suite", archived_filter)
    if exclude_run_ids:
        stmt = stmt.where(SuiteRun.id.not_in(exclude_run_ids))
    if only_run_ids is not None:
        stmt = stmt.where(SuiteRun.id.in_(only_run_ids))
    rows = (await db.execute(stmt.order_by(SuiteRun.created_at.desc(), SuiteRun.id.desc()).limit(limit + 1))).all()
    has_more = len(rows) > limit
    items = [
        _task_item(
            task_type="suite",
            run_id=run.id,
            source_id=run.suite_id,
            project_id=suite_project_id,
            project_name=project_name,
            name=suite_name,
            status_value=run.status,
            created_at=run.created_at,
            duration_ms=run.duration_ms,
            error_message=run.error_message,
            detail_path=f"/suites?project_id={suite_project_id}&run_id={run.id}",
            metadata={"suite_id": run.suite_id},
        )
        for run, suite_name, suite_project_id, project_name in rows[:limit]
    ]
    return items, has_more


async def _collect_plan_tasks(
    db: AsyncSession,
    user: User,
    project_id: int | None,
    status_filter: StatusFilter,
    limit: int,
    archived_filter: str | None = None,
    exclude_run_ids: set[int] | None = None,
    only_run_ids: set[int] | None = None,
) -> tuple[list[WorkbenchTaskItem], bool]:
    if only_run_ids is not None and not only_run_ids:
        return [], False
    stmt = (
        select(PlanRun, TestPlan.name, TestPlan.project_id, Project.name)
        .join(TestPlan, PlanRun.plan_id == TestPlan.id)
        .join(Project, TestPlan.project_id == Project.id)
    )
    stmt = _project_filter(stmt, TestPlan.project_id, user, project_id)
    stmt = _apply_status_filter(stmt, PlanRun.status, status_filter)
    stmt = _apply_archived_filter(stmt, PlanRun.id, "plan", archived_filter)
    if exclude_run_ids:
        stmt = stmt.where(PlanRun.id.not_in(exclude_run_ids))
    if only_run_ids is not None:
        stmt = stmt.where(PlanRun.id.in_(only_run_ids))
    rows = (await db.execute(stmt.order_by(PlanRun.created_at.desc(), PlanRun.id.desc()).limit(limit + 1))).all()
    has_more = len(rows) > limit
    items = [
        _task_item(
            task_type="plan",
            run_id=run.id,
            source_id=run.plan_id,
            project_id=plan_project_id,
            project_name=project_name,
            name=plan_name,
            status_value=run.status,
            created_at=run.created_at,
            duration_ms=run.duration_ms,
            error_message=run.error_message,
            detail_path=f"/plans?project_id={plan_project_id}&run_id={run.id}",
            metadata={"plan_id": run.plan_id},
        )
        for run, plan_name, plan_project_id, project_name in rows[:limit]
    ]
    return items, has_more


async def _collect_android_tasks(
    db: AsyncSession,
    user: User,
    project_id: int | None,
    status_filter: StatusFilter,
    limit: int,
    archived_filter: str | None = None,
    exclude_run_ids: set[int] | None = None,
    only_run_ids: set[int] | None = None,
) -> tuple[list[WorkbenchTaskItem], bool]:
    if only_run_ids is not None and not only_run_ids:
        return [], False
    stmt = (
        select(MobileSpecialRun, MobileSpecialTask.name, MobileSpecialTask.project_id, Project.name)
        .join(MobileSpecialTask, MobileSpecialRun.task_id == MobileSpecialTask.id)
        .join(Project, MobileSpecialTask.project_id == Project.id)
    )
    stmt = _project_filter(stmt, MobileSpecialTask.project_id, user, project_id)
    stmt = _apply_status_filter(stmt, MobileSpecialRun.status, status_filter)
    stmt = _apply_archived_filter(stmt, MobileSpecialRun.id, "android", archived_filter)
    if exclude_run_ids:
        stmt = stmt.where(MobileSpecialRun.id.not_in(exclude_run_ids))
    if only_run_ids is not None:
        stmt = stmt.where(MobileSpecialRun.id.in_(only_run_ids))
    rows = (
        await db.execute(stmt.order_by(MobileSpecialRun.created_at.desc(), MobileSpecialRun.id.desc()).limit(limit + 1))
    ).all()
    has_more = len(rows) > limit
    items = [
        _task_item(
            task_type="android",
            run_id=run.id,
            source_id=run.task_id,
            project_id=task_project_id,
            project_name=project_name,
            name=task_name,
            status_value=run.status,
            created_at=run.created_at,
            started_at=run.started_at,
            finished_at=run.finished_at,
            duration_ms=run.duration_ms,
            error_message=(run.summary_json or {}).get("error_message") if isinstance(run.summary_json, dict) else None,
            detail_path=f"/mobile-special/reports/{run.id}?project_id={task_project_id}",
            metadata={"task_id": run.task_id, "task_type": _enum_value(run.task_type)},
        )
        for run, task_name, task_project_id, project_name in rows[:limit]
    ]
    return items, has_more


async def _collect_performance_tasks(
    db: AsyncSession,
    user: User,
    project_id: int | None,
    status_filter: StatusFilter,
    limit: int,
    archived_filter: str | None = None,
    exclude_run_ids: set[int] | None = None,
    only_run_ids: set[int] | None = None,
) -> tuple[list[WorkbenchTaskItem], bool]:
    if only_run_ids is not None and not only_run_ids:
        return [], False
    stmt = (
        select(
            PerformanceRun,
            PerformanceTest.name,
            PerformanceTest.executor,
            PerformanceRun.project_id,
            Project.name,
        )
        .join(PerformanceTest, PerformanceRun.performance_test_id == PerformanceTest.id)
        .join(Project, PerformanceRun.project_id == Project.id)
    )
    stmt = _project_filter(stmt, PerformanceRun.project_id, user, project_id)
    stmt = _apply_status_filter(stmt, PerformanceRun.status, status_filter)
    stmt = _apply_archived_filter(stmt, PerformanceRun.id, "performance", archived_filter)
    if exclude_run_ids:
        stmt = stmt.where(PerformanceRun.id.not_in(exclude_run_ids))
    if only_run_ids is not None:
        stmt = stmt.where(PerformanceRun.id.in_(only_run_ids))
    rows = (
        await db.execute(stmt.order_by(PerformanceRun.created_at.desc(), PerformanceRun.id.desc()).limit(limit + 1))
    ).all()
    has_more = len(rows) > limit
    items = [
        _task_item(
            task_type="performance",
            run_id=run.id,
            source_id=run.performance_test_id,
            project_id=run_project_id,
            project_name=project_name,
            name=test_name,
            status_value=run.status,
            created_at=run.created_at,
            started_at=run.started_at,
            finished_at=run.finished_at,
            duration_ms=run.duration_ms,
            error_message=run.error_message,
            detail_path=f"/system/performance?project_id={run_project_id}&run_id={run.id}",
            metadata={"performance_test_id": run.performance_test_id, "executor": test_executor},
        )
        for run, test_name, test_executor, run_project_id, project_name in rows[:limit]
    ]
    return items, has_more


async def _collect_tasks(
    db: AsyncSession,
    user: User,
    project_id: int | None,
    status_filter: StatusFilter,
    task_type: str | None,
    limit: int,
    offset: int = 0,
    archived_filter: str | None = None,
    exclude_run_ids: dict[str, set[int]] | None = None,
    only_run_ids: dict[str, set[int]] | None = None,
) -> tuple[list[WorkbenchTaskItem], bool]:
    collectors = {
        "case": _collect_case_tasks,
        "suite": _collect_suite_tasks,
        "plan": _collect_plan_tasks,
        "android": _collect_android_tasks,
        "performance": _collect_performance_tasks,
    }
    selected = [task_type] if task_type else list(collectors)
    collected: list[WorkbenchTaskItem] = []
    has_more = False
    per_type_limit = min(limit + offset, 1200)
    for selected_type in selected:
        if only_run_ids is not None and not only_run_ids.get(selected_type):
            continue
        kwargs: dict[str, Any] = {}
        if archived_filter is not None:
            kwargs["archived_filter"] = archived_filter
        if exclude_run_ids and exclude_run_ids.get(selected_type):
            kwargs["exclude_run_ids"] = exclude_run_ids[selected_type]
        if only_run_ids and only_run_ids.get(selected_type):
            kwargs["only_run_ids"] = only_run_ids[selected_type]

        collector_fn = collectors[selected_type]
        try:
            items, source_has_more = await collector_fn(
                db,
                user,
                project_id,
                _status_filter_for_type(status_filter, selected_type),
                per_type_limit,
                **kwargs,
            )
        except TypeError:
            items, source_has_more = await collector_fn(
                db,
                user,
                project_id,
                _status_filter_for_type(status_filter, selected_type),
                per_type_limit,
            )
        collected.extend(items)
        has_more = has_more or source_has_more

    if archived_filter in {"only", "all"}:
        task_keys = [(item.task_type, item.run_id) for item in collected]
        if task_keys:
            archived_stmt = select(
                WorkbenchArchivedTask.task_type,
                WorkbenchArchivedTask.run_id,
                WorkbenchArchivedTask.archived_at,
            ).where(
                or_(
                    *(
                        and_(WorkbenchArchivedTask.task_type == t_type, WorkbenchArchivedTask.run_id == r_id)
                        for t_type, r_id in set(task_keys)
                    )
                )
            )
            archived_rows = (await db.execute(archived_stmt)).all()
            archived_map = {(row[0], row[1]): row[2] for row in archived_rows}

            for item in collected:
                key = (item.task_type, item.run_id)
                if key in archived_map:
                    item.is_archived = True
                    item.archived_at = archived_map[key]

    collected.sort(key=lambda item: item.created_at or datetime.min.replace(tzinfo=timezone.utc), reverse=True)
    page_end = offset + limit
    if len(collected) > page_end:
        has_more = True
    page = collected[offset:page_end]
    await _apply_task_action_permissions(db, user, page)
    return page, has_more


async def _apply_task_action_permissions(
    db: AsyncSession,
    user: User,
    tasks: list[WorkbenchTaskItem],
) -> None:
    """Mask state-level actions that the current user cannot actually execute."""
    actionable_tasks = [task for task in tasks if task.can_retry or task.can_stop]
    project_ids = {task.project_id for task in actionable_tasks if task.project_id is not None}
    if not project_ids:
        return

    if user.role == UserRole.admin:
        stmt = select(Project.id).where(Project.id.in_(project_ids), Project.status != "archived")
    else:
        stmt = (
            select(UserProject.project_id)
            .join(Project, Project.id == UserProject.project_id)
            .where(
                UserProject.user_id == user.id,
                UserProject.project_id.in_(project_ids),
                UserProject.role.in_([ProjectRole.owner, ProjectRole.editor]),
                Project.status != "archived",
            )
        )
    writable_project_ids = set((await db.execute(stmt)).scalars().all())
    can_operate_special = user.role in {UserRole.admin, UserRole.engineer}
    for task in actionable_tasks:
        if task.project_id not in writable_project_ids:
            task.can_retry = False
            task.can_stop = False
        elif task.task_type in {"android", "performance"} and not can_operate_special:
            task.can_retry = False
            task.can_stop = False


async def _count_tasks(
    db: AsyncSession,
    user: User,
    project_id: int | None,
    status_filter: StatusFilter,
    task_type: str | None,
    archived_filter: str | None = None,
    exclude_run_ids: dict[str, set[int]] | None = None,
    only_run_ids: dict[str, set[int]] | None = None,
) -> int:
    selected = [task_type] if task_type else ["case", "suite", "plan", "android", "performance"]
    total = 0
    if "case" in selected and (only_run_ids is None or only_run_ids.get("case")):
        stmt = (
            select(func.count(TestRun.id))
            .join(TestCase, TestRun.case_id == TestCase.id)
            .join(Module, TestCase.module_id == Module.id)
        )
        stmt = _project_filter(stmt, Module.project_id, user, project_id)
        stmt = _apply_status_filter(stmt, TestRun.status, _status_filter_for_type(status_filter, "case"))
        stmt = _apply_archived_filter(stmt, TestRun.id, "case", archived_filter)
        if exclude_run_ids and exclude_run_ids.get("case"):
            stmt = stmt.where(TestRun.id.not_in(exclude_run_ids["case"]))
        if only_run_ids and only_run_ids.get("case"):
            stmt = stmt.where(TestRun.id.in_(only_run_ids["case"]))
        total += int((await db.execute(stmt)).scalar_one() or 0)
    if "suite" in selected and (only_run_ids is None or only_run_ids.get("suite")):
        stmt = select(func.count(SuiteRun.id)).join(TestSuite, SuiteRun.suite_id == TestSuite.id)
        stmt = _project_filter(stmt, TestSuite.project_id, user, project_id)
        stmt = _apply_status_filter(stmt, SuiteRun.status, _status_filter_for_type(status_filter, "suite"))
        stmt = _apply_archived_filter(stmt, SuiteRun.id, "suite", archived_filter)
        if exclude_run_ids and exclude_run_ids.get("suite"):
            stmt = stmt.where(SuiteRun.id.not_in(exclude_run_ids["suite"]))
        if only_run_ids and only_run_ids.get("suite"):
            stmt = stmt.where(SuiteRun.id.in_(only_run_ids["suite"]))
        total += int((await db.execute(stmt)).scalar_one() or 0)
    if "plan" in selected and (only_run_ids is None or only_run_ids.get("plan")):
        stmt = select(func.count(PlanRun.id)).join(TestPlan, PlanRun.plan_id == TestPlan.id)
        stmt = _project_filter(stmt, TestPlan.project_id, user, project_id)
        stmt = _apply_status_filter(stmt, PlanRun.status, _status_filter_for_type(status_filter, "plan"))
        stmt = _apply_archived_filter(stmt, PlanRun.id, "plan", archived_filter)
        if exclude_run_ids and exclude_run_ids.get("plan"):
            stmt = stmt.where(PlanRun.id.not_in(exclude_run_ids["plan"]))
        if only_run_ids and only_run_ids.get("plan"):
            stmt = stmt.where(PlanRun.id.in_(only_run_ids["plan"]))
        total += int((await db.execute(stmt)).scalar_one() or 0)
    if "android" in selected and (only_run_ids is None or only_run_ids.get("android")):
        stmt = select(func.count(MobileSpecialRun.id)).join(
            MobileSpecialTask, MobileSpecialRun.task_id == MobileSpecialTask.id
        )
        stmt = _project_filter(stmt, MobileSpecialTask.project_id, user, project_id)
        stmt = _apply_status_filter(
            stmt,
            MobileSpecialRun.status,
            _status_filter_for_type(status_filter, "android"),
        )
        stmt = _apply_archived_filter(stmt, MobileSpecialRun.id, "android", archived_filter)
        if exclude_run_ids and exclude_run_ids.get("android"):
            stmt = stmt.where(MobileSpecialRun.id.not_in(exclude_run_ids["android"]))
        if only_run_ids and only_run_ids.get("android"):
            stmt = stmt.where(MobileSpecialRun.id.in_(only_run_ids["android"]))
        total += int((await db.execute(stmt)).scalar_one() or 0)
    if "performance" in selected and (only_run_ids is None or only_run_ids.get("performance")):
        stmt = select(func.count(PerformanceRun.id)).join(
            PerformanceTest, PerformanceRun.performance_test_id == PerformanceTest.id
        )
        stmt = _project_filter(stmt, PerformanceRun.project_id, user, project_id)
        stmt = _apply_status_filter(
            stmt,
            PerformanceRun.status,
            _status_filter_for_type(status_filter, "performance"),
        )
        stmt = _apply_archived_filter(stmt, PerformanceRun.id, "performance", archived_filter)
        if exclude_run_ids and exclude_run_ids.get("performance"):
            stmt = stmt.where(PerformanceRun.id.not_in(exclude_run_ids["performance"]))
        if only_run_ids and only_run_ids.get("performance"):
            stmt = stmt.where(PerformanceRun.id.in_(only_run_ids["performance"]))
        total += int((await db.execute(stmt)).scalar_one() or 0)
    return total


async def _get_active_snooze_map(
    db: AsyncSession,
    user: User,
    project_id: int | None,
) -> dict[str, WorkbenchTodoSnooze]:
    now_utc = datetime.now(timezone.utc)
    snooze_stmt = select(WorkbenchTodoSnooze).where(
        WorkbenchTodoSnooze.user_id == user.id,
        or_(WorkbenchTodoSnooze.snoozed_until.is_(None), WorkbenchTodoSnooze.snoozed_until > now_utc),
    )
    if project_id is not None:
        snooze_stmt = snooze_stmt.where(
            or_(WorkbenchTodoSnooze.project_id.is_(None), WorkbenchTodoSnooze.project_id == project_id)
        )
    rows = (await db.execute(snooze_stmt)).scalars().all()
    return {row.todo_id: row for row in rows}


def _parse_snoozed_targets(active_ids: set[str]) -> dict[str, Any]:
    reviews = {int(x.split(":")[1]) for x in active_ids if x.startswith("review:") and x.split(":")[1].isdigit()}
    plans = {int(x.split(":")[1]) for x in active_ids if x.startswith("overdue-plan:") and x.split(":")[1].isdigit()}
    devices = {int(x.split(":")[1]) for x in active_ids if x.startswith("device:") and x.split(":")[1].isdigit()}
    failed_by_type: dict[str, set[int]] = {}
    for x in active_ids:
        if x.startswith("failed-run:"):
            parts = x.split(":")
            if len(parts) == 3 and parts[2].isdigit():
                failed_by_type.setdefault(parts[1], set()).add(int(parts[2]))
    return {
        "reviews": reviews,
        "plans": plans,
        "devices": devices,
        "failed_by_type": failed_by_type,
    }


async def _count_todos(
    db: AsyncSession,
    user: User,
    project_id: int | None,
    snooze_filter: str | None = None,
) -> dict[str, int]:
    active_snooze_map: dict[str, WorkbenchTodoSnooze] = {}
    targets: dict[str, Any] = {"reviews": set(), "plans": set(), "devices": set(), "failed_by_type": {}}
    if snooze_filter in {"only", "exclude", "all"}:
        active_snooze_map = await _get_active_snooze_map(db, user, project_id)
        targets = _parse_snoozed_targets(set(active_snooze_map.keys()))

    review_stmt = (
        select(func.count(TestCase.id))
        .join(Module, TestCase.module_id == Module.id)
        .where(TestCase.review_status == "pending")
    )
    review_stmt = _project_filter(review_stmt, Module.project_id, user, project_id)
    if snooze_filter == "exclude" and targets["reviews"]:
        review_stmt = review_stmt.where(TestCase.id.not_in(targets["reviews"]))
    elif snooze_filter == "only":
        if not targets["reviews"]:
            review_stmt = review_stmt.where(false())
        else:
            review_stmt = review_stmt.where(TestCase.id.in_(targets["reviews"]))
    pending_reviews = int((await db.execute(review_stmt)).scalar_one() or 0)

    failed_exclude = targets["failed_by_type"] if snooze_filter == "exclude" else None
    failed_only = targets["failed_by_type"] if snooze_filter == "only" else None
    try:
        failed_runs = await _count_tasks(
            db,
            user,
            project_id,
            _FAILED_STATUSES,
            None,
            archived_filter="exclude",
            exclude_run_ids=failed_exclude,
            only_run_ids=failed_only,
        )
    except TypeError:
        failed_runs = await _count_tasks(
            db,
            user,
            project_id,
            _FAILED_STATUSES,
            None,
        )

    overdue_stmt = select(func.count(TestPlan.id)).where(
        TestPlan.status == "active",
        TestPlan.is_enabled.is_(True),
        TestPlan.schedule_type == ScheduleType.cron,
        TestPlan.next_run_at.is_not(None),
        TestPlan.next_run_at < datetime.now(timezone.utc),
    )
    overdue_stmt = _project_filter(overdue_stmt, TestPlan.project_id, user, project_id)
    if snooze_filter == "exclude" and targets["plans"]:
        overdue_stmt = overdue_stmt.where(TestPlan.id.not_in(targets["plans"]))
    elif snooze_filter == "only":
        if not targets["plans"]:
            overdue_stmt = overdue_stmt.where(false())
        else:
            overdue_stmt = overdue_stmt.where(TestPlan.id.in_(targets["plans"]))
    overdue_plans = int((await db.execute(overdue_stmt)).scalar_one() or 0)

    device_anomalies = 0
    if user.role in {UserRole.admin, UserRole.engineer} and project_id is None:
        stale_before = datetime.now(timezone.utc) - timedelta(minutes=5)
        device_stmt = select(func.count(Device.id)).where(
            Device.status == DeviceStatus.offline,
            Device.last_seen_at.is_not(None),
            Device.last_seen_at < stale_before,
        )
        if snooze_filter == "exclude" and targets["devices"]:
            device_stmt = device_stmt.where(Device.id.not_in(targets["devices"]))
        elif snooze_filter == "only":
            if not targets["devices"]:
                device_stmt = device_stmt.where(false())
            else:
                device_stmt = device_stmt.where(Device.id.in_(targets["devices"]))
        device_anomalies = int((await db.execute(device_stmt)).scalar_one() or 0)

    try:
        active_tasks = await _count_tasks(db, user, project_id, _ACTIVE_STATUSES, None, archived_filter="exclude")
    except TypeError:
        active_tasks = await _count_tasks(db, user, project_id, _ACTIVE_STATUSES, None)

    total_todos = pending_reviews + failed_runs + overdue_plans + device_anomalies
    res = {
        "pending_reviews": pending_reviews,
        "failed_runs": failed_runs,
        "overdue_plans": overdue_plans,
        "device_anomalies": device_anomalies,
        "active_tasks": active_tasks,
        "total_todos": total_todos,
    }
    if snooze_filter in {"only", "exclude", "all"}:
        res["snoozed_todos"] = len(active_snooze_map)
    return res


async def _collect_todos(
    db: AsyncSession,
    user: User,
    project_id: int | None,
    limit: int,
    offset: int = 0,
    snooze_filter: str | None = None,
) -> tuple[list[WorkbenchTodoItem], bool]:
    todos: list[WorkbenchTodoItem] = []
    has_more = False
    source_limit = min(limit + offset, 1200)

    active_snooze_map: dict[str, WorkbenchTodoSnooze] = {}
    targets: dict[str, Any] = {"reviews": set(), "plans": set(), "devices": set(), "failed_by_type": {}}
    if snooze_filter in {"only", "exclude", "all"}:
        active_snooze_map = await _get_active_snooze_map(db, user, project_id)
        targets = _parse_snoozed_targets(set(active_snooze_map.keys()))

    review_stmt = (
        select(TestCase, Project.name, Module.project_id)
        .join(Module, TestCase.module_id == Module.id)
        .join(Project, Module.project_id == Project.id)
        .where(TestCase.review_status == "pending")
    )
    review_stmt = _project_filter(review_stmt, Module.project_id, user, project_id)
    if snooze_filter == "exclude" and targets["reviews"]:
        review_stmt = review_stmt.where(TestCase.id.not_in(targets["reviews"]))
    elif snooze_filter == "only":
        if not targets["reviews"]:
            review_stmt = review_stmt.where(false())
        else:
            review_stmt = review_stmt.where(TestCase.id.in_(targets["reviews"]))
    review_rows = (
        await db.execute(review_stmt.order_by(TestCase.updated_at.asc(), TestCase.id.asc()).limit(source_limit + 1))
    ).all()
    has_more = has_more or len(review_rows) > source_limit
    todos.extend(
        WorkbenchTodoItem(
            id=f"review:{case.id}",
            kind="case_review",
            priority="medium",
            project_id=case_project_id,
            project_name=project_name,
            title=f"用例待评审：{case.name}",
            description="请完成用例评审，确认后才可进入执行流程。",
            status="pending",
            created_at=case.updated_at,
            path=f"/cases/{case.id}",
            metadata={"case_id": case.id, "review_status": case.review_status},
        )
        for case, project_name, case_project_id in review_rows[:source_limit]
    )

    failed_exclude = targets["failed_by_type"] if snooze_filter == "exclude" else None
    failed_only = targets["failed_by_type"] if snooze_filter == "only" else None
    try:
        failed_tasks, failed_has_more = await _collect_tasks(
            db,
            user,
            project_id,
            _FAILED_STATUSES,
            None,
            source_limit,
            archived_filter="exclude",
            exclude_run_ids=failed_exclude,
            only_run_ids=failed_only,
        )
    except TypeError:
        failed_tasks, failed_has_more = await _collect_tasks(
            db,
            user,
            project_id,
            _FAILED_STATUSES,
            None,
            source_limit,
        )
    has_more = has_more or failed_has_more
    todos.extend(
        WorkbenchTodoItem(
            id=f"failed-run:{task.task_type}:{task.run_id}",
            kind="failed_run",
            priority="high",
            project_id=task.project_id,
            project_name=task.project_name,
            title=f"失败运行待处理：{task.name}",
            description=task.error_message or "请查看执行详情并决定重试或创建缺陷。",
            status=task.status,
            created_at=task.created_at,
            path=task.detail_path,
            metadata={
                "run_id": task.run_id,
                "source_id": task.source_id,
                "task_type": task.task_type,
                "can_retry": task.can_retry,
            },
        )
        for task in failed_tasks
    )

    now = datetime.now(timezone.utc)
    overdue_stmt = (
        select(TestPlan, Project.name)
        .join(Project, TestPlan.project_id == Project.id)
        .where(
            TestPlan.status == "active",
            TestPlan.is_enabled.is_(True),
            TestPlan.schedule_type == ScheduleType.cron,
            TestPlan.next_run_at.is_not(None),
            TestPlan.next_run_at < now,
        )
    )
    overdue_stmt = _project_filter(overdue_stmt, TestPlan.project_id, user, project_id)
    if snooze_filter == "exclude" and targets["plans"]:
        overdue_stmt = overdue_stmt.where(TestPlan.id.not_in(targets["plans"]))
    elif snooze_filter == "only":
        if not targets["plans"]:
            overdue_stmt = overdue_stmt.where(false())
        else:
            overdue_stmt = overdue_stmt.where(TestPlan.id.in_(targets["plans"]))
    overdue_rows = (await db.execute(overdue_stmt.order_by(TestPlan.next_run_at.asc()).limit(source_limit + 1))).all()
    has_more = has_more or len(overdue_rows) > source_limit
    todos.extend(
        WorkbenchTodoItem(
            id=f"overdue-plan:{plan.id}",
            kind="overdue_plan",
            priority="high",
            project_id=plan.project_id,
            project_name=project_name,
            title=f"计划逾期：{plan.name}",
            description="计划已超过下次执行时间，请检查调度配置或立即执行。",
            status="overdue",
            created_at=plan.updated_at,
            due_at=plan.next_run_at,
            path="/plans",
            metadata={"plan_id": plan.id, "next_run_at": plan.next_run_at.isoformat()},
        )
        for plan, project_name in overdue_rows[:source_limit]
    )

    if user.role in {UserRole.admin, UserRole.engineer} and project_id is None:
        stale_before = now - timedelta(minutes=5)
        device_stmt = select(Device).where(
            Device.status == DeviceStatus.offline,
            Device.last_seen_at.is_not(None),
            Device.last_seen_at < stale_before,
        )
        if snooze_filter == "exclude" and targets["devices"]:
            device_stmt = device_stmt.where(Device.id.not_in(targets["devices"]))
        elif snooze_filter == "only":
            if not targets["devices"]:
                device_stmt = device_stmt.where(false())
            else:
                device_stmt = device_stmt.where(Device.id.in_(targets["devices"]))
        device_rows = (
            (await db.execute(device_stmt.order_by(Device.last_seen_at.desc()).limit(source_limit + 1))).scalars().all()
        )
        has_more = has_more or len(device_rows) > source_limit
        todos.extend(
            WorkbenchTodoItem(
                id=f"device:{device.id}",
                kind="device_anomaly",
                priority="medium",
                project_id=None,
                project_name=None,
                title=f"设备异常：{device.name or device.serial}",
                description="设备最近曾在线但当前离线，请检查 ADB、Android Worker 或设备连接。",
                status=_enum_value(device.status),
                created_at=device.last_seen_at,
                path="/devices",
                metadata={"device_id": device.id, "serial": device.serial},
            )
            for device in device_rows[:source_limit]
        )

    if snooze_filter in {"only", "all"}:
        for item in todos:
            if item.id in active_snooze_map:
                item.is_snoozed = True
                item.snooze_reason = active_snooze_map[item.id].reason
                item.snoozed_until = active_snooze_map[item.id].snoozed_until

    priority_order = {"high": 0, "medium": 1, "low": 2}
    todos.sort(key=lambda item: (priority_order[item.priority], item.due_at or item.created_at or now))
    page_end = offset + limit
    if len(todos) > page_end:
        has_more = True
    return todos[offset:page_end], has_more


@router.get("/workbench/overview", response_model=WorkbenchOverviewOut)
async def get_workbench_overview(
    project_id: int | None = Query(None, ge=1),
    todo_limit: int = Query(50, ge=1, le=100),
    todo_offset: int = Query(0, ge=0, le=1000),
    task_limit: int = Query(50, ge=1, le=100),
    snooze_filter: str = Query("exclude", pattern="^(exclude|only|all)$"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if project_id is not None:
        await assert_project_access(db, current_user, project_id, ProjectRole.viewer)
    generated_at = datetime.now(timezone.utc)
    todos, has_more_todos = await _collect_todos(db, current_user, project_id, todo_limit, todo_offset, snooze_filter)
    try:
        tasks, has_more_tasks = await _collect_tasks(
            db, current_user, project_id, None, None, task_limit, archived_filter="exclude"
        )
    except TypeError:
        tasks, has_more_tasks = await _collect_tasks(db, current_user, project_id, None, None, task_limit)
    counts = await _count_todos(db, current_user, project_id, snooze_filter)
    counts["returned_tasks"] = len(tasks)
    return WorkbenchOverviewOut(
        generated_at=generated_at,
        project_id=project_id,
        counts=counts,
        todos=todos,
        tasks=tasks,
        has_more_todos=has_more_todos,
        has_more_tasks=has_more_tasks,
    )


@router.get("/workbench/tasks", response_model=WorkbenchTaskPageOut)
async def list_workbench_tasks(
    project_id: int | None = Query(None, ge=1),
    status_filter: str | None = Query(None, alias="status"),
    task_type: str | None = Query(None),
    archived_filter: str = Query("exclude", pattern="^(exclude|only|all)$"),
    limit: int = Query(100, ge=1, le=200),
    offset: int = Query(0, ge=0, le=1000),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if project_id is not None:
        await assert_project_access(db, current_user, project_id, ProjectRole.viewer)
    if task_type is not None and task_type not in _TASK_TYPES:
        raise HTTPException(status_code=400, detail="任务类型不支持")
    generated_at = datetime.now(timezone.utc)
    items, has_more = await _collect_tasks(
        db, current_user, project_id, status_filter, task_type, limit, offset, archived_filter
    )
    total = await _count_tasks(db, current_user, project_id, status_filter, task_type, archived_filter)
    return WorkbenchTaskPageOut(
        generated_at=generated_at,
        project_id=project_id,
        status_filter=status_filter,
        task_type=task_type,
        items=items,
        total=total,
        has_more=has_more,
    )


async def _workbench_task_project_id(db: AsyncSession, task_type: WorkbenchTaskType, run_id: int) -> int | None:
    """Resolve the project before dispatching a cross-domain diagnosis request."""

    if task_type == "case":
        run = await db.get(TestRun, run_id)
        case = await db.get(TestCase, run.case_id) if run else None
        module = await db.get(Module, case.module_id) if case else None
        return module.project_id if module else None
    if task_type == "suite":
        run = await db.get(SuiteRun, run_id)
        suite = await db.get(TestSuite, run.suite_id) if run else None
        return suite.project_id if suite else None
    if task_type == "plan":
        run = await db.get(PlanRun, run_id)
        plan = await db.get(TestPlan, run.plan_id) if run else None
        return plan.project_id if plan else None
    if task_type == "android":
        run = await db.get(MobileSpecialRun, run_id)
        task = await db.get(MobileSpecialTask, run.task_id) if run else None
        return task.project_id if task else None
    run = await db.get(PerformanceRun, run_id)
    return run.project_id if run else None


async def _workbench_task_status(db: AsyncSession, task_type: WorkbenchTaskType, run_id: int) -> str | None:
    model: Any = {
        "case": TestRun,
        "suite": SuiteRun,
        "plan": PlanRun,
        "android": MobileSpecialRun,
        "performance": PerformanceRun,
    }[task_type]
    run: Any = await db.get(model, run_id)
    return _enum_value(run.status) if run is not None else None


@router.post(
    "/workbench/tasks/{task_type}/{run_id}/failure-diagnosis",
    response_model=FailureDiagnosisOut,
)
async def diagnose_workbench_task_failure(
    task_type: WorkbenchTaskType,
    run_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    project_id = await _workbench_task_project_id(db, task_type, run_id)
    if project_id is None:
        raise HTTPException(status_code=404, detail="任务不存在")
    await assert_project_access(db, current_user, project_id, ProjectRole.viewer)
    diagnosis = await generate_workbench_failure_diagnosis(db, task_type, run_id)
    if diagnosis is None:
        raise HTTPException(status_code=404, detail="任务不存在")
    return diagnosis


async def _retry_task(ref: WorkbenchTaskRef, db: AsyncSession, user: User) -> WorkbenchTaskActionOut:
    if ref.task_type == "case":
        from app.api.v1.cases.runs import trigger_run

        source = await db.get(TestRun, ref.run_id)
        if source is None:
            raise HTTPException(status_code=404, detail="用例运行不存在")
        case = await db.get(TestCase, source.case_id)
        if case is None:
            raise HTTPException(status_code=404, detail="用例不存在")
        module = await db.get(Module, case.module_id)
        if module is None:
            raise HTTPException(status_code=404, detail="用例模块不存在")
        await assert_project_access(db, user, module.project_id, ProjectRole.editor)
        _ensure_retryable(ref, source.status)
        result = await trigger_run(source.case_id, RunTriggerRequest(), db, user)
    elif ref.task_type == "suite":
        from app.api.v1.suites import trigger_suite_run

        source = await db.get(SuiteRun, ref.run_id)
        if source is None:
            raise HTTPException(status_code=404, detail="套件运行不存在")
        suite = await db.get(TestSuite, source.suite_id)
        if suite is None:
            raise HTTPException(status_code=404, detail="套件不存在")
        await assert_project_access(db, user, suite.project_id, ProjectRole.editor)
        _ensure_retryable(ref, source.status)
        result = await trigger_suite_run(source.suite_id, SuiteRunTrigger(), db, user)
    elif ref.task_type == "plan":
        from app.api.v1.plans import trigger_plan_run

        source = await db.get(PlanRun, ref.run_id)
        if source is None:
            raise HTTPException(status_code=404, detail="计划运行不存在")
        plan = await db.get(TestPlan, source.plan_id)
        if plan is None:
            raise HTTPException(status_code=404, detail="计划不存在")
        await assert_project_access(db, user, plan.project_id, ProjectRole.editor)
        _ensure_retryable(ref, source.status)
        result = await trigger_plan_run(source.plan_id, PlanRunTrigger(), db, user)
    elif ref.task_type == "android":
        if user.role not in {UserRole.admin, UserRole.engineer}:
            raise HTTPException(status_code=403, detail="Android 任务需要工程师权限")
        from app.api.v1.mobile_special import trigger_task_run

        source = await db.get(MobileSpecialRun, ref.run_id)
        if source is None:
            raise HTTPException(status_code=404, detail="Android 运行不存在")
        task = await db.get(MobileSpecialTask, source.task_id)
        if task is None:
            raise HTTPException(status_code=404, detail="Android 任务不存在")
        await assert_project_access(db, user, task.project_id, ProjectRole.editor)
        _ensure_retryable(ref, source.status)
        result = await trigger_task_run(
            source.task_id,
            MobileRunTriggerRequest(device_id=source.device_id, app_package=source.app_package),
            db,
            user,
        )
    else:
        if user.role not in {UserRole.admin, UserRole.engineer}:
            raise HTTPException(status_code=403, detail="性能任务需要工程师权限")
        from app.api.v1.performance import trigger_performance_run

        source = await db.get(PerformanceRun, ref.run_id)
        if source is None:
            raise HTTPException(status_code=404, detail="性能运行不存在")
        performance_test = await db.get(PerformanceTest, source.performance_test_id)
        if performance_test is None:
            raise HTTPException(status_code=404, detail="压测定义不存在")
        await assert_project_access(db, user, performance_test.project_id, ProjectRole.editor)
        _ensure_retryable(ref, source.status)
        result = await trigger_performance_run(
            source.performance_test_id,
            PerformanceRunTrigger(
                environment_id=source.environment_id,
                performance_node_id=source.performance_node_id,
                options=dict(source.options_snapshot or {}),
            ),
            db,
            user,
        )
    return WorkbenchTaskActionOut(
        action="retry",
        task_type=ref.task_type,
        run_id=ref.run_id,
        new_run_id=getattr(result, "id", None),
        status=_enum_value(getattr(result, "status", "pending")),
        message="已创建新的执行任务",
    )


def _ensure_retryable(ref: WorkbenchTaskRef, status_value: Any) -> None:
    current_status = _enum_value(status_value)
    decision = decide_execution_action(ref.task_type, current_status, "retry")
    if not decision.allowed:
        raise HTTPException(
            status_code=409,
            detail=execution_action_rejection_detail(ref.task_type, current_status, "retry", decision),
        )


async def _stop_task(ref: WorkbenchTaskRef, db: AsyncSession, user: User) -> WorkbenchTaskActionOut:
    if ref.task_type == "android":
        if user.role not in {UserRole.admin, UserRole.engineer}:
            raise HTTPException(status_code=403, detail="Android 任务需要工程师权限")
        from app.api.v1.mobile_special import stop_run

        result = await stop_run(ref.run_id, db, user)
    elif ref.task_type == "performance":
        if user.role not in {UserRole.admin, UserRole.engineer}:
            raise HTTPException(status_code=403, detail="性能任务需要工程师权限")
        from app.api.v1.performance import stop_performance_run

        result = await stop_performance_run(ref.run_id, db, user)
    else:
        raise HTTPException(status_code=409, detail="当前任务类型暂不支持终止，请查看任务详情")
    return WorkbenchTaskActionOut(
        action="stop",
        task_type=ref.task_type,
        run_id=ref.run_id,
        status=_enum_value(getattr(result, "status", "cancelled")),
        message="已发送终止请求",
    )


async def _execute_action(
    action: WorkbenchAction,
    ref: WorkbenchTaskRef,
    db: AsyncSession,
    user: User,
) -> WorkbenchTaskActionOut:
    if action == "retry":
        return await _retry_task(ref, db, user)
    return await _stop_task(ref, db, user)


async def _execute_idempotent_action(
    action: WorkbenchAction,
    ref: WorkbenchTaskRef,
    db: AsyncSession,
    user: User,
) -> WorkbenchTaskActionOut:
    command_id = normalize_execution_command_id(
        ref.command_id,
        action=action,
        task_type=ref.task_type,
        run_id=ref.run_id,
    )
    project_id = await _workbench_task_project_id(db, ref.task_type, ref.run_id)
    if project_id is None:
        raise HTTPException(status_code=404, detail="任务不存在")
    await assert_project_access(db, user, project_id, ProjectRole.editor)
    if ref.task_type in {"android", "performance"} and user.role not in {UserRole.admin, UserRole.engineer}:
        raise HTTPException(status_code=403, detail="专项任务操作需要工程师权限")
    source_status = await _workbench_task_status(db, ref.task_type, ref.run_id)
    if source_status is None:
        raise HTTPException(status_code=404, detail="任务不存在")
    claim = await claim_execution_command(
        db,
        user_id=user.id,
        command_id=command_id,
        action=action,
        task_type=ref.task_type,
        run_id=ref.run_id,
        project_id=project_id,
        source_status=source_status,
    )
    if claim.replay_response is not None:
        return WorkbenchTaskActionOut.model_validate(
            {**claim.replay_response, "command_id": command_id, "replayed": True}
        )

    try:
        result = await _execute_action(action, ref, db, user)
    except HTTPException as exc:
        await fail_execution_command(
            db,
            claim.command,
            status_code=exc.status_code,
            detail=str(exc.detail),
            username=user.username,
        )
        raise
    except Exception:
        await mark_execution_command_indeterminate(
            db,
            claim.command,
            username=user.username,
        )
        raise

    result.command_id = command_id
    await complete_execution_command(
        db,
        claim.command,
        response=result.model_dump(mode="json"),
        username=user.username,
    )
    return result


@router.post("/workbench/tasks/{task_type}/{run_id}/retry", response_model=WorkbenchTaskActionOut)
async def retry_workbench_task(
    task_type: WorkbenchTaskType,
    run_id: int,
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return await _execute_idempotent_action(
        "retry",
        WorkbenchTaskRef(task_type=task_type, run_id=run_id, command_id=idempotency_key),
        db,
        current_user,
    )


@router.post("/workbench/tasks/{task_type}/{run_id}/stop", response_model=WorkbenchTaskActionOut)
async def stop_workbench_task(
    task_type: WorkbenchTaskType,
    run_id: int,
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return await _execute_idempotent_action(
        "stop",
        WorkbenchTaskRef(task_type=task_type, run_id=run_id, command_id=idempotency_key),
        db,
        current_user,
    )


@router.post("/workbench/tasks/batch-action", response_model=WorkbenchBatchActionOut)
async def batch_workbench_action(
    body: WorkbenchBatchActionIn,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    results: list[WorkbenchTaskActionOut] = []
    failures: list[dict] = []
    for ref in body.tasks:
        try:
            results.append(await _execute_idempotent_action(body.action, ref, db, current_user))
        except HTTPException as exc:
            failures.append(
                {
                    "task_type": ref.task_type,
                    "run_id": ref.run_id,
                    "command_id": ref.command_id,
                    "detail": str(exc.detail),
                }
            )
        except Exception:
            await db.rollback()
            failures.append({"task_type": ref.task_type, "run_id": ref.run_id, "detail": "执行统一任务操作失败"})
    return WorkbenchBatchActionOut(
        action=body.action,
        requested=len(body.tasks),
        processed=len(results),
        results=results,
        failures=failures,
    )


async def _resolve_todo_project_and_authorize(db: AsyncSession, user: User, todo_id: str) -> int | None:
    parts = todo_id.split(":")
    prefix = parts[0]
    if prefix == "review" and len(parts) == 2 and parts[1].isdigit():
        case_id = int(parts[1])
        case = await db.get(TestCase, case_id)
        if not case:
            raise HTTPException(status_code=404, detail="待办用例不存在")
        module = await db.get(Module, case.module_id) if case.module_id else None
        if not module:
            raise HTTPException(status_code=404, detail="用例模块不存在")
        await assert_project_access(db, user, module.project_id, ProjectRole.viewer)
        return module.project_id
    elif prefix == "failed-run" and len(parts) == 3 and parts[2].isdigit():
        task_type_str, run_id = parts[1], int(parts[2])
        if task_type_str not in _TASK_TYPES:
            raise HTTPException(status_code=400, detail="任务类型不支持")
        task_type = cast(WorkbenchTaskType, task_type_str)
        project_id = await _workbench_task_project_id(db, task_type, run_id)
        status_val = await _workbench_task_status(db, task_type, run_id)
        if status_val is None:
            raise HTTPException(status_code=404, detail="执行记录不存在")
        if project_id is not None:
            await assert_project_access(db, user, project_id, ProjectRole.viewer)
        elif user.role not in {UserRole.admin, UserRole.engineer}:
            raise HTTPException(status_code=403, detail="无权操作此待办")
        return project_id
    elif prefix == "overdue-plan" and len(parts) == 2 and parts[1].isdigit():
        plan_id = int(parts[1])
        plan = await db.get(TestPlan, plan_id)
        if not plan:
            raise HTTPException(status_code=404, detail="测试计划不存在")
        await assert_project_access(db, user, plan.project_id, ProjectRole.viewer)
        return plan.project_id
    elif prefix == "device" and len(parts) == 2 and parts[1].isdigit():
        device_id = int(parts[1])
        device = await db.get(Device, device_id)
        if not device:
            raise HTTPException(status_code=404, detail="设备不存在")
        if user.role not in {UserRole.admin, UserRole.engineer}:
            raise HTTPException(status_code=403, detail="仅管理员或工程师可操作设备待办")
        return None
    else:
        raise HTTPException(status_code=400, detail="待办 ID 格式无效")


async def _batch_resolve_task_projects_and_authorize(
    db: AsyncSession,
    user: User,
    tasks: list[WorkbenchTaskRef],
    required_role: ProjectRole = ProjectRole.editor,
) -> dict[tuple[str, int], int | None]:
    """Batch verify existence of runs and authorize editor/admin access."""
    grouped: dict[str, set[int]] = {}
    for t in tasks:
        grouped.setdefault(t.task_type, set()).add(t.run_id)

    task_project_map: dict[tuple[str, int], int | None] = {}

    if "case" in grouped:
        run_ids = grouped["case"]
        stmt = (
            select(TestRun.id, Module.project_id)
            .outerjoin(TestCase, TestRun.case_id == TestCase.id)
            .outerjoin(Module, TestCase.module_id == Module.id)
            .where(TestRun.id.in_(run_ids))
        )
        for r_id, p_id in (await db.execute(stmt)).all():
            task_project_map[("case", r_id)] = p_id

    if "suite" in grouped:
        run_ids = grouped["suite"]
        stmt = (
            select(SuiteRun.id, TestSuite.project_id)
            .outerjoin(TestSuite, SuiteRun.suite_id == TestSuite.id)
            .where(SuiteRun.id.in_(run_ids))
        )
        for r_id, p_id in (await db.execute(stmt)).all():
            task_project_map[("suite", r_id)] = p_id

    if "plan" in grouped:
        run_ids = grouped["plan"]
        stmt = (
            select(PlanRun.id, TestPlan.project_id)
            .outerjoin(TestPlan, PlanRun.plan_id == TestPlan.id)
            .where(PlanRun.id.in_(run_ids))
        )
        for r_id, p_id in (await db.execute(stmt)).all():
            task_project_map[("plan", r_id)] = p_id

    if "android" in grouped:
        run_ids = grouped["android"]
        stmt = (
            select(MobileSpecialRun.id, MobileSpecialTask.project_id)
            .outerjoin(MobileSpecialTask, MobileSpecialRun.task_id == MobileSpecialTask.id)
            .where(MobileSpecialRun.id.in_(run_ids))
        )
        for r_id, p_id in (await db.execute(stmt)).all():
            task_project_map[("android", r_id)] = p_id

    if "performance" in grouped:
        run_ids = grouped["performance"]
        stmt = select(PerformanceRun.id, PerformanceRun.project_id).where(PerformanceRun.id.in_(run_ids))
        for r_id, p_id in (await db.execute(stmt)).all():
            task_project_map[("performance", r_id)] = p_id

    for t in tasks:
        key = (t.task_type, t.run_id)
        if key not in task_project_map:
            raise HTTPException(status_code=404, detail=f"任务记录不存在: {t.task_type} #{t.run_id}")

    distinct_projects = {p_id for p_id in task_project_map.values() if p_id is not None}
    for p_id in distinct_projects:
        await assert_project_access(db, user, p_id, required_role)

    if None in task_project_map.values() and user.role != UserRole.admin:
        raise HTTPException(status_code=403, detail="仅管理员可操作无项目归属的任务")

    return task_project_map


@router.post("/workbench/todos/{todo_id:path}/snooze", response_model=WorkbenchTodoSnoozeOut)
async def snooze_workbench_todo(
    todo_id: str,
    body: WorkbenchTodoSnoozeIn = WorkbenchTodoSnoozeIn(),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    project_id = await _resolve_todo_project_and_authorize(db, current_user, todo_id)
    now = datetime.now(timezone.utc)
    snoozed_until = now + timedelta(hours=body.duration_hours) if body.duration_hours > 0 else None

    stmt = select(WorkbenchTodoSnooze).where(
        WorkbenchTodoSnooze.user_id == current_user.id,
        WorkbenchTodoSnooze.todo_id == todo_id,
    )
    existing = (await db.execute(stmt)).scalar_one_or_none()
    if existing:
        existing.reason = body.reason.strip() if body.reason else None
        existing.snoozed_until = snoozed_until
        existing.project_id = project_id
        existing.created_at = now
        snooze_obj = existing
    else:
        snooze_obj = WorkbenchTodoSnooze(
            todo_id=todo_id,
            user_id=current_user.id,
            project_id=project_id,
            reason=body.reason.strip() if body.reason else None,
            snoozed_until=snoozed_until,
            created_at=now,
        )
        db.add(snooze_obj)
    await db.commit()
    await db.refresh(snooze_obj)
    return WorkbenchTodoSnoozeOut(
        todo_id=snooze_obj.todo_id,
        user_id=snooze_obj.user_id,
        reason=snooze_obj.reason,
        snoozed_until=snooze_obj.snoozed_until,
        created_at=snooze_obj.created_at,
    )


@router.delete("/workbench/todos/{todo_id:path}/snooze")
@router.post("/workbench/todos/{todo_id:path}/unsnooze")
async def unsnooze_workbench_todo(
    todo_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    stmt = select(WorkbenchTodoSnooze).where(
        WorkbenchTodoSnooze.user_id == current_user.id,
        WorkbenchTodoSnooze.todo_id == todo_id,
    )
    existing = (await db.execute(stmt)).scalar_one_or_none()
    if existing:
        if existing.project_id is not None:
            await assert_project_access(db, current_user, existing.project_id, ProjectRole.viewer)
        await db.delete(existing)
        await db.commit()
    return {"status": "ok", "todo_id": todo_id, "unsnoozed": True}


@router.post("/workbench/tasks/archive", response_model=WorkbenchTaskArchiveOut)
async def archive_workbench_tasks(
    body: WorkbenchTaskArchiveIn,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    task_project_map = await _batch_resolve_task_projects_and_authorize(
        db, current_user, body.tasks, ProjectRole.editor
    )
    now = datetime.now(timezone.utc)
    task_keys = {(t.task_type, t.run_id) for t in body.tasks}
    existing_stmt = select(WorkbenchArchivedTask.task_type, WorkbenchArchivedTask.run_id).where(
        or_(
            *(
                and_(WorkbenchArchivedTask.task_type == t_type, WorkbenchArchivedTask.run_id == r_id)
                for t_type, r_id in task_keys
            )
        )
    )
    existing_keys = set((await db.execute(existing_stmt)).all())

    processed = 0
    for task_ref in body.tasks:
        key = (task_ref.task_type, task_ref.run_id)
        if key not in existing_keys:
            db.add(
                WorkbenchArchivedTask(
                    task_type=task_ref.task_type,
                    run_id=task_ref.run_id,
                    project_id=task_project_map[key],
                    archived_by=current_user.id,
                    archived_at=now,
                )
            )
            existing_keys.add(key)
            processed += 1
    await db.commit()
    return WorkbenchTaskArchiveOut(processed=processed, archived=True)


@router.post("/workbench/tasks/unarchive", response_model=WorkbenchTaskArchiveOut)
async def unarchive_workbench_tasks(
    body: WorkbenchTaskArchiveIn,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    await _batch_resolve_task_projects_and_authorize(db, current_user, body.tasks, ProjectRole.editor)
    task_keys = {(t.task_type, t.run_id) for t in body.tasks}
    delete_stmt = select(WorkbenchArchivedTask).where(
        or_(
            *(
                and_(WorkbenchArchivedTask.task_type == t_type, WorkbenchArchivedTask.run_id == r_id)
                for t_type, r_id in task_keys
            )
        )
    )
    existing_rows = (await db.execute(delete_stmt)).scalars().all()
    processed = len(existing_rows)
    for row in existing_rows:
        await db.delete(row)
    await db.commit()
    return WorkbenchTaskArchiveOut(processed=processed, archived=False)
