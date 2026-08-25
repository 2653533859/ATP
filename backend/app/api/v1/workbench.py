"""Workbench aggregation and unified task actions.

The workbench is intentionally a read/dispatch layer.  It does not introduce a
second execution engine or a second source of truth for run state: list data is
read from the existing run tables and actions delegate to the existing domain
endpoints, so their project-role and executor checks remain authoritative.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import false, func, select
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
from app.models.user_project import ProjectRole
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
    WorkbenchTaskItem,
    WorkbenchTaskPageOut,
    WorkbenchTaskRef,
    WorkbenchTaskType,
    WorkbenchTodoItem,
)
from app.services.project_scope import scope_to_visible_projects
from app.services.workbench_diagnosis import generate_workbench_failure_diagnosis

router = APIRouter(tags=["工作台"])

_TASK_TYPES = {"case", "suite", "plan", "android", "performance"}
_ACTIVE_STATUSES = {"pending", "running", "cancelling"}
_FAILED_STATUSES = {"failed", "error", "cancelled", "stopped"}
_STATUS_VALUES_BY_TYPE = {
    "case": {status.value for status in RunStatus},
    "suite": {status.value for status in SuiteRunStatus},
    "plan": {status.value for status in PlanRunStatus},
    "android": {status.value for status in MobileRunStatus},
    "performance": {status.value for status in PerformanceRunStatus},
}
_RETRYABLE_STATUSES = {
    "case": {"failed", "error", "skipped"},
    "suite": {"failed", "error"},
    "plan": {"failed", "error"},
    "android": {"failed", "stopped"},
    "performance": {"failed", "cancelled"},
}
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
    can_retry = status in _RETRYABLE_STATUSES.get(task_type, set())
    can_stop = task_type in {"android", "performance"} and status in {"pending", "running"}
    if task_type == "android":
        can_stop = status in {"pending", "running"}
    if task_type == "performance":
        can_retry = status in {"failed", "cancelled"}
        can_stop = status in {"pending", "running"}

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
) -> tuple[list[WorkbenchTaskItem], bool]:
    stmt = (
        select(TestRun, TestCase.name, Module.project_id, Project.name)
        .join(TestCase, TestRun.case_id == TestCase.id)
        .join(Module, TestCase.module_id == Module.id)
        .join(Project, Module.project_id == Project.id)
    )
    stmt = _project_filter(stmt, Module.project_id, user, project_id)
    stmt = _apply_status_filter(stmt, TestRun.status, status_filter)
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
            detail_path=f"/runs/{run.id}",
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
) -> tuple[list[WorkbenchTaskItem], bool]:
    stmt = (
        select(SuiteRun, TestSuite.name, TestSuite.project_id, Project.name)
        .join(TestSuite, SuiteRun.suite_id == TestSuite.id)
        .join(Project, TestSuite.project_id == Project.id)
    )
    stmt = _project_filter(stmt, TestSuite.project_id, user, project_id)
    stmt = _apply_status_filter(stmt, SuiteRun.status, status_filter)
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
            detail_path=f"/suites?project_id={suite_project_id}",
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
) -> tuple[list[WorkbenchTaskItem], bool]:
    stmt = (
        select(PlanRun, TestPlan.name, TestPlan.project_id, Project.name)
        .join(TestPlan, PlanRun.plan_id == TestPlan.id)
        .join(Project, TestPlan.project_id == Project.id)
    )
    stmt = _project_filter(stmt, TestPlan.project_id, user, project_id)
    stmt = _apply_status_filter(stmt, PlanRun.status, status_filter)
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
            detail_path=f"/plans?project_id={plan_project_id}",
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
) -> tuple[list[WorkbenchTaskItem], bool]:
    stmt = (
        select(MobileSpecialRun, MobileSpecialTask.name, MobileSpecialTask.project_id, Project.name)
        .join(MobileSpecialTask, MobileSpecialRun.task_id == MobileSpecialTask.id)
        .join(Project, MobileSpecialTask.project_id == Project.id)
    )
    stmt = _project_filter(stmt, MobileSpecialTask.project_id, user, project_id)
    stmt = _apply_status_filter(stmt, MobileSpecialRun.status, status_filter)
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
            detail_path=f"/mobile-special/reports/{run.id}",
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
) -> tuple[list[WorkbenchTaskItem], bool]:
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
            detail_path=f"/system/performance?project_id={run_project_id}",
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
    per_type_limit = min(limit, 100)
    for selected_type in selected:
        items, source_has_more = await collectors[selected_type](
            db,
            user,
            project_id,
            _status_filter_for_type(status_filter, selected_type),
            per_type_limit,
        )
        collected.extend(items)
        has_more = has_more or source_has_more
    collected.sort(key=lambda item: item.created_at or datetime.min.replace(tzinfo=timezone.utc), reverse=True)
    if len(collected) > limit:
        has_more = True
    return collected[:limit], has_more


async def _count_tasks(
    db: AsyncSession,
    user: User,
    project_id: int | None,
    status_filter: StatusFilter,
    task_type: str | None,
) -> int:
    selected = [task_type] if task_type else ["case", "suite", "plan", "android", "performance"]
    total = 0
    if "case" in selected:
        stmt = (
            select(func.count(TestRun.id))
            .join(TestCase, TestRun.case_id == TestCase.id)
            .join(Module, TestCase.module_id == Module.id)
        )
        stmt = _project_filter(stmt, Module.project_id, user, project_id)
        total += int(
            (
                await db.execute(
                    _apply_status_filter(stmt, TestRun.status, _status_filter_for_type(status_filter, "case"))
                )
            ).scalar_one()
            or 0
        )
    if "suite" in selected:
        stmt = select(func.count(SuiteRun.id)).join(TestSuite, SuiteRun.suite_id == TestSuite.id)
        stmt = _project_filter(stmt, TestSuite.project_id, user, project_id)
        total += int(
            (
                await db.execute(
                    _apply_status_filter(stmt, SuiteRun.status, _status_filter_for_type(status_filter, "suite"))
                )
            ).scalar_one()
            or 0
        )
    if "plan" in selected:
        stmt = select(func.count(PlanRun.id)).join(TestPlan, PlanRun.plan_id == TestPlan.id)
        stmt = _project_filter(stmt, TestPlan.project_id, user, project_id)
        total += int(
            (
                await db.execute(
                    _apply_status_filter(stmt, PlanRun.status, _status_filter_for_type(status_filter, "plan"))
                )
            ).scalar_one()
            or 0
        )
    if "android" in selected:
        stmt = select(func.count(MobileSpecialRun.id)).join(
            MobileSpecialTask, MobileSpecialRun.task_id == MobileSpecialTask.id
        )
        stmt = _project_filter(stmt, MobileSpecialTask.project_id, user, project_id)
        total += int(
            (
                await db.execute(
                    _apply_status_filter(
                        stmt,
                        MobileSpecialRun.status,
                        _status_filter_for_type(status_filter, "android"),
                    )
                )
            ).scalar_one()
            or 0
        )
    if "performance" in selected:
        stmt = select(func.count(PerformanceRun.id)).join(
            PerformanceTest, PerformanceRun.performance_test_id == PerformanceTest.id
        )
        stmt = _project_filter(stmt, PerformanceRun.project_id, user, project_id)
        total += int(
            (
                await db.execute(
                    _apply_status_filter(
                        stmt,
                        PerformanceRun.status,
                        _status_filter_for_type(status_filter, "performance"),
                    )
                )
            ).scalar_one()
            or 0
        )
    return total


async def _count_todos(db: AsyncSession, user: User, project_id: int | None) -> dict[str, int]:
    review_stmt = (
        select(func.count(TestCase.id))
        .join(Module, TestCase.module_id == Module.id)
        .where(TestCase.review_status == "pending")
    )
    review_stmt = _project_filter(review_stmt, Module.project_id, user, project_id)
    pending_reviews = int((await db.execute(review_stmt)).scalar_one() or 0)

    failed_runs = await _count_tasks(db, user, project_id, _FAILED_STATUSES, None)

    overdue_stmt = select(func.count(TestPlan.id)).where(
        TestPlan.status == "active",
        TestPlan.is_enabled.is_(True),
        TestPlan.schedule_type == ScheduleType.cron,
        TestPlan.next_run_at.is_not(None),
        TestPlan.next_run_at < datetime.now(timezone.utc),
    )
    overdue_stmt = _project_filter(overdue_stmt, TestPlan.project_id, user, project_id)
    overdue_plans = int((await db.execute(overdue_stmt)).scalar_one() or 0)

    device_anomalies = 0
    if user.role in {UserRole.admin, UserRole.engineer} and project_id is None:
        stale_before = datetime.now(timezone.utc) - timedelta(minutes=5)
        device_stmt = select(func.count(Device.id)).where(
            Device.status == DeviceStatus.offline,
            Device.last_seen_at.is_not(None),
            Device.last_seen_at < stale_before,
        )
        device_anomalies = int((await db.execute(device_stmt)).scalar_one() or 0)

    active_tasks = await _count_tasks(db, user, project_id, _ACTIVE_STATUSES, None)
    total_todos = pending_reviews + failed_runs + overdue_plans + device_anomalies
    return {
        "pending_reviews": pending_reviews,
        "failed_runs": failed_runs,
        "overdue_plans": overdue_plans,
        "device_anomalies": device_anomalies,
        "active_tasks": active_tasks,
        "total_todos": total_todos,
    }


async def _collect_todos(
    db: AsyncSession,
    user: User,
    project_id: int | None,
    limit: int,
) -> tuple[list[WorkbenchTodoItem], bool]:
    todos: list[WorkbenchTodoItem] = []
    has_more = False

    review_stmt = (
        select(TestCase, Project.name, Module.project_id)
        .join(Module, TestCase.module_id == Module.id)
        .join(Project, Module.project_id == Project.id)
        .where(TestCase.review_status == "pending")
    )
    review_stmt = _project_filter(review_stmt, Module.project_id, user, project_id)
    review_rows = (
        await db.execute(review_stmt.order_by(TestCase.updated_at.asc(), TestCase.id.asc()).limit(limit + 1))
    ).all()
    has_more = has_more or len(review_rows) > limit
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
        for case, project_name, case_project_id in review_rows[:limit]
    )

    failed_tasks, failed_has_more = await _collect_tasks(
        db,
        user,
        project_id,
        _FAILED_STATUSES,
        None,
        limit,
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
    overdue_rows = (await db.execute(overdue_stmt.order_by(TestPlan.next_run_at.asc()).limit(limit + 1))).all()
    has_more = has_more or len(overdue_rows) > limit
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
        for plan, project_name in overdue_rows[:limit]
    )

    if user.role in {UserRole.admin, UserRole.engineer} and project_id is None:
        stale_before = now - timedelta(minutes=5)
        device_stmt = select(Device).where(
            Device.status == DeviceStatus.offline,
            Device.last_seen_at.is_not(None),
            Device.last_seen_at < stale_before,
        )
        device_rows = (
            (await db.execute(device_stmt.order_by(Device.last_seen_at.desc()).limit(limit + 1))).scalars().all()
        )
        has_more = has_more or len(device_rows) > limit
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
            for device in device_rows[:limit]
        )

    priority_order = {"high": 0, "medium": 1, "low": 2}
    todos.sort(key=lambda item: (priority_order[item.priority], item.due_at or item.created_at or now))
    return todos[:limit], has_more or len(todos) > limit


@router.get("/workbench/overview", response_model=WorkbenchOverviewOut)
async def get_workbench_overview(
    project_id: int | None = Query(None, ge=1),
    todo_limit: int = Query(50, ge=1, le=100),
    task_limit: int = Query(50, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if project_id is not None:
        await assert_project_access(db, current_user, project_id, ProjectRole.viewer)
    generated_at = datetime.now(timezone.utc)
    todos, has_more_todos = await _collect_todos(db, current_user, project_id, todo_limit)
    tasks, has_more_tasks = await _collect_tasks(db, current_user, project_id, None, None, task_limit)
    counts = await _count_todos(db, current_user, project_id)
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
    limit: int = Query(100, ge=1, le=200),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if project_id is not None:
        await assert_project_access(db, current_user, project_id, ProjectRole.viewer)
    if task_type is not None and task_type not in _TASK_TYPES:
        raise HTTPException(status_code=400, detail="任务类型不支持")
    generated_at = datetime.now(timezone.utc)
    items, has_more = await _collect_tasks(db, current_user, project_id, status_filter, task_type, limit)
    total = await _count_tasks(db, current_user, project_id, status_filter, task_type)
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
    if current_status not in _RETRYABLE_STATUSES[ref.task_type]:
        raise HTTPException(
            status_code=409,
            detail=f"{ref.task_type} 任务当前状态为 {current_status}，不可重试",
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


@router.post("/workbench/tasks/{task_type}/{run_id}/retry", response_model=WorkbenchTaskActionOut)
async def retry_workbench_task(
    task_type: WorkbenchTaskType,
    run_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return await _execute_action("retry", WorkbenchTaskRef(task_type=task_type, run_id=run_id), db, current_user)


@router.post("/workbench/tasks/{task_type}/{run_id}/stop", response_model=WorkbenchTaskActionOut)
async def stop_workbench_task(
    task_type: WorkbenchTaskType,
    run_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return await _execute_action("stop", WorkbenchTaskRef(task_type=task_type, run_id=run_id), db, current_user)


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
            results.append(await _execute_action(body.action, ref, db, current_user))
        except HTTPException as exc:
            failures.append({"task_type": ref.task_type, "run_id": ref.run_id, "detail": str(exc.detail)})
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
