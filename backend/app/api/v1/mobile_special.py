"""Mobile Special Testing API endpoints."""

import asyncio
import logging
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy import select, func, case as sql_case
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.cache_decorator import cached_json
from app.core.database import get_db
from app.core.redis_client import get_json_cache, set_json_cache
from app.models.mobile_special import (
    MobileSpecialTask,
    MobileSpecialRun,
    MobileMetricSample,
    MobileIncident,
    MobileRunArtifact,
    RunStatus,
    TaskType,
    TriggerType,
)
from app.schemas.mobile_special import (
    MobileSpecialTaskCreate,
    MobileSpecialTaskUpdate,
    MobileSpecialTaskOut,
    MobileSpecialRunOut,
    MobileSpecialRunListItem,
    MobileMetricSampleOut,
    MobileIncidentOut,
    MobileRunArtifactOut,
    RunTriggerRequest,
)
from app.api.deps import (
    assert_project_access,
    get_current_user,
    require_engineer,
)
from app.models.user_project import ProjectRole
from app.services.mobile_special_control import request_cancel
from app.services.project_scope import scope_to_visible_projects

router = APIRouter(prefix="/mobile-special", tags=["Android专项测试"])
logger = logging.getLogger(__name__)


def _calc_next_run(cron_expression: str | None) -> datetime | None:
    if not cron_expression:
        return None
    try:
        from croniter import croniter

        now = datetime.now(timezone.utc)
        cron = croniter(cron_expression, now)
        return cron.get_next(datetime)
    except Exception:
        return None


def _refresh_schedule_state(task: MobileSpecialTask) -> None:
    if task.schedule_enabled and task.cron_expression:
        task.next_run_at = _calc_next_run(task.cron_expression)
    else:
        task.next_run_at = None


_MOBILE_STATS_CACHE_TTL = 60


def _mobile_stats_cache_key(name: str, **kwargs) -> str:
    items = ":".join(f"{key}={kwargs[key]}" for key in sorted(kwargs))
    return f"atp:mobile-stats:{name}:{items}"


async def _safe_get_mobile_stats_cache(key: str):
    try:
        return await get_json_cache(key)
    except Exception:
        logger.warning("failed to get mobile stats cache: %s", key, exc_info=True)
        return None


async def _safe_set_mobile_stats_cache(key: str, value) -> None:
    try:
        await set_json_cache(key, value, _MOBILE_STATS_CACHE_TTL)
    except Exception:
        logger.warning("failed to set mobile stats cache: %s", key, exc_info=True)


def _build_mobile_stats_cache_key(name: str, *fields: str):
    def builder(**kwargs) -> str:
        values = {field: kwargs.get(field) for field in fields}
        user = kwargs.get("user") or kwargs.get("_")
        values["user_id"] = getattr(user, "id", None)
        return _mobile_stats_cache_key(name, **values)

    return builder


def _identity(value):
    return value


def _build_run_list_item(run: MobileSpecialRun, task_name: str | None) -> MobileSpecialRunListItem:
    data = MobileSpecialRunOut.model_validate(run, from_attributes=True).model_dump()
    data["task_name"] = task_name
    return MobileSpecialRunListItem(**data)


def _scope_mobile_runs(stmt, user, project_id: int | None = None):
    stmt = stmt.join(MobileSpecialTask, MobileSpecialRun.task_id == MobileSpecialTask.id)
    return scope_to_visible_projects(stmt, MobileSpecialTask.project_id, user, project_id)


async def _get_run_with_access(
    db: AsyncSession,
    user,
    run_id: int,
    min_role: ProjectRole = ProjectRole.viewer,
) -> MobileSpecialRun:
    run = await db.get(MobileSpecialRun, run_id)
    if not run:
        raise HTTPException(status_code=404, detail="Run not found")
    task = await db.get(MobileSpecialTask, run.task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    await assert_project_access(db, user, task.project_id, min_role)
    return run


# ---- Task CRUD ----


@router.get("/tasks", response_model=list[MobileSpecialTaskOut])
async def list_tasks(
    project_id: Optional[int] = None,
    task_type: Optional[TaskType] = None,
    db: AsyncSession = Depends(get_db),
    user=Depends(get_current_user),
):
    """List all mobile special tasks, optionally filtered by project and task type."""
    if project_id is not None:
        await assert_project_access(db, user, project_id, ProjectRole.viewer)
    q = scope_to_visible_projects(select(MobileSpecialTask), MobileSpecialTask.project_id, user, project_id).order_by(
        MobileSpecialTask.updated_at.desc()
    )
    if task_type is not None:
        q = q.where(MobileSpecialTask.task_type == task_type)
    result = await db.execute(q)
    return result.scalars().all()


@router.post("/tasks", response_model=MobileSpecialTaskOut, status_code=status.HTTP_201_CREATED)
async def create_task(
    body: MobileSpecialTaskCreate,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(require_engineer),
):
    """Create a new mobile special task."""
    await assert_project_access(db, current_user, body.project_id, ProjectRole.editor)
    # created_by 以当前登录用户为准；schema 中的同名字段仅为兼容内部导入，须排除避免键冲突
    task = MobileSpecialTask(
        **body.model_dump(exclude={"created_by"}),
        created_by=current_user.id,
    )
    _refresh_schedule_state(task)
    db.add(task)
    await db.commit()
    await db.refresh(task)
    return task


@router.get("/tasks/{task_id}", response_model=MobileSpecialTaskOut)
async def get_task(
    task_id: int,
    db: AsyncSession = Depends(get_db),
    user=Depends(get_current_user),
):
    """Get a specific mobile special task."""
    task = await db.get(MobileSpecialTask, task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    await assert_project_access(db, user, task.project_id, ProjectRole.viewer)
    return task


@router.patch("/tasks/{task_id}", response_model=MobileSpecialTaskOut)
async def update_task(
    task_id: int,
    body: MobileSpecialTaskUpdate,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(require_engineer),
):
    """Update a mobile special task."""
    task = await db.get(MobileSpecialTask, task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    await assert_project_access(db, current_user, task.project_id, ProjectRole.editor)

    update_data = body.model_dump(exclude_none=True)
    for k, v in update_data.items():
        setattr(task, k, v)
    task.updated_by = current_user.id
    _refresh_schedule_state(task)

    await db.commit()
    await db.refresh(task)
    return task


@router.delete("/tasks/{task_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_task(
    task_id: int,
    db: AsyncSession = Depends(get_db),
    user=Depends(require_engineer),
):
    """Delete a mobile special task."""
    task = await db.get(MobileSpecialTask, task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    await assert_project_access(db, user, task.project_id, ProjectRole.editor)
    await db.delete(task)
    await db.commit()


# ---- Run trigger / stop ----


@router.post("/tasks/{task_id}/run", response_model=MobileSpecialRunOut, status_code=status.HTTP_201_CREATED)
async def trigger_task_run(
    task_id: int,
    body: RunTriggerRequest,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(require_engineer),
):
    """Manually trigger a mobile special task run."""
    task = await db.get(MobileSpecialTask, task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    await assert_project_access(db, current_user, task.project_id, ProjectRole.editor)

    config = dict(task.config_json or {})
    selected_device_id = body.device_id if body.device_id is not None else task.device_id
    if body.device_id is not None:
        config["device_id"] = body.device_id
    if body.app_package:
        config["app_package"] = body.app_package

    run = MobileSpecialRun(
        task_id=task.id,
        task_type=task.task_type,
        status=RunStatus.pending,
        trigger_type=TriggerType.manual,
        triggered_by=current_user.id,
        config_snapshot=config,
        device_id=selected_device_id,
        app_package=body.app_package or task.app_package,
    )
    db.add(run)
    await db.commit()
    await db.refresh(run)

    # 异步触发 Celery 任务
    from app.worker.tasks_mobile_special import run_mobile_special_task

    run_mobile_special_task.delay(run.id)

    return run


@router.post("/runs/{run_id}/stop", response_model=MobileSpecialRunOut)
async def stop_run(
    run_id: int,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(require_engineer),
):
    """Stop a running mobile special task."""
    run = await _get_run_with_access(db, current_user, run_id, ProjectRole.editor)

    if run.status not in [RunStatus.pending, RunStatus.running]:
        raise HTTPException(status_code=400, detail=f"Cannot stop run in status: {run.status.value}")

    try:
        await asyncio.to_thread(request_cancel, run.id)
    except Exception as exc:
        raise HTTPException(status_code=503, detail="无法发送停止信号，请稍后重试") from exc

    run.status = RunStatus.stopped
    run.finished_at = datetime.now(timezone.utc)
    await db.commit()
    await db.refresh(run)
    return run


# ---- Runs / Reports ----


@router.get("/runs", response_model=list[MobileSpecialRunListItem])
async def list_runs(
    task_id: Optional[int] = None,
    task_type: Optional[TaskType] = None,
    status_filter: Optional[RunStatus] = None,
    project_id: Optional[int] = None,
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    db: AsyncSession = Depends(get_db),
    user=Depends(get_current_user),
):
    """List mobile special runs with filters."""
    q = (
        select(MobileSpecialRun, MobileSpecialTask.name.label("task_name"))
        .outerjoin(MobileSpecialTask, MobileSpecialRun.task_id == MobileSpecialTask.id)
        .order_by(MobileSpecialRun.created_at.desc())
        .offset(offset)
        .limit(limit)
    )
    if task_id is not None:
        q = q.where(MobileSpecialRun.task_id == task_id)
    if task_type is not None:
        q = q.where(MobileSpecialRun.task_type == task_type)
    if status_filter is not None:
        q = q.where(MobileSpecialRun.status == status_filter)
    if project_id is not None:
        await assert_project_access(db, user, project_id, ProjectRole.viewer)
        q = q.where(MobileSpecialTask.project_id == project_id)
    else:
        q = scope_to_visible_projects(q, MobileSpecialTask.project_id, user)

    result = await db.execute(q)
    rows = result.all()
    return [_build_run_list_item(row[0], row.task_name) for row in rows]


@router.get("/runs/{run_id}", response_model=MobileSpecialRunOut)
async def get_run(
    run_id: int,
    db: AsyncSession = Depends(get_db),
    user=Depends(get_current_user),
):
    """Get a specific run."""
    return await _get_run_with_access(db, user, run_id)


@router.get("/runs/{run_id}/summary", response_model=dict)
async def get_run_summary(
    run_id: int,
    db: AsyncSession = Depends(get_db),
    user=Depends(get_current_user),
):
    """Get the summary JSON for a run."""
    run = await _get_run_with_access(db, user, run_id)
    return run.summary_json or {}


@router.get("/runs/{run_id}/samples", response_model=list[MobileMetricSampleOut])
async def list_run_samples(
    run_id: int,
    metric_type: Optional[str] = None,
    limit: int = Query(default=1000, ge=1, le=10000),
    db: AsyncSession = Depends(get_db),
    user=Depends(get_current_user),
):
    """Get metric samples for a run."""
    await _get_run_with_access(db, user, run_id)

    q = (
        select(MobileMetricSample)
        .where(MobileMetricSample.run_id == run_id)
        .order_by(MobileMetricSample.sample_time.asc())
        .limit(limit)
    )
    if metric_type is not None:
        q = q.where(MobileMetricSample.metric_type == metric_type)

    result = await db.execute(q)
    return result.scalars().all()


@router.get("/runs/{run_id}/incidents", response_model=list[MobileIncidentOut])
async def list_run_incidents(
    run_id: int,
    db: AsyncSession = Depends(get_db),
    user=Depends(get_current_user),
):
    """Get incidents for a run."""
    await _get_run_with_access(db, user, run_id)

    q = select(MobileIncident).where(MobileIncident.run_id == run_id)
    result = await db.execute(q)
    return result.scalars().all()


@router.get("/runs/{run_id}/artifacts", response_model=list[MobileRunArtifactOut])
async def list_run_artifacts(
    run_id: int,
    db: AsyncSession = Depends(get_db),
    user=Depends(get_current_user),
):
    """Get artifacts for a run."""
    await _get_run_with_access(db, user, run_id)

    q = select(MobileRunArtifact).where(MobileRunArtifact.run_id == run_id)
    result = await db.execute(q)
    return result.scalars().all()


# ---- Export ----


@router.get("/runs/{run_id}/export/csv")
async def export_run_csv(
    run_id: int,
    db: AsyncSession = Depends(get_db),
    user=Depends(get_current_user),
):
    """Export metric samples of a run as CSV."""
    await _get_run_with_access(db, user, run_id)

    q = (
        select(MobileMetricSample)
        .where(MobileMetricSample.run_id == run_id)
        .order_by(MobileMetricSample.sample_time.asc())
    )
    result = await db.execute(q)
    samples = result.scalars().all()

    if not samples:
        raise HTTPException(status_code=404, detail="No samples found for this run")

    lines = ["id,run_id,sample_time,metric_type,metric_value,source"]
    for s in samples:
        lines.append(
            f"{s.id},{s.run_id},{s.sample_time.isoformat()},{s.metric_type.value},{s.metric_value},{s.source or ''}"
        )

    csv_content = "\n".join(lines)
    filename = f"mobile_run_{run_id}_metrics.csv"

    from fastapi.responses import Response

    return Response(
        content=csv_content,
        media_type="text/csv",
        headers={"Content-Disposition": f"attachment; filename={filename}"},
    )


@router.get("/runs/{run_id}/export/json")
async def export_run_json(
    run_id: int,
    db: AsyncSession = Depends(get_db),
    user=Depends(get_current_user),
):
    """Export full run report as JSON (samples + incidents + summary)."""
    run = await _get_run_with_access(db, user, run_id)

    # Fetch task name
    task = await db.get(MobileSpecialTask, run.task_id)
    task_name = task.name if task else None

    # Fetch samples
    samples_q = (
        select(MobileMetricSample)
        .where(MobileMetricSample.run_id == run_id)
        .order_by(MobileMetricSample.sample_time.asc())
    )
    samples_result = await db.execute(samples_q)
    samples = samples_result.scalars().all()

    # Fetch incidents
    incidents_q = select(MobileIncident).where(MobileIncident.run_id == run_id)
    incidents_result = await db.execute(incidents_q)
    incidents = incidents_result.scalars().all()

    # Fetch artifacts
    artifacts_q = select(MobileRunArtifact).where(MobileRunArtifact.run_id == run_id)
    artifacts_result = await db.execute(artifacts_q)
    artifacts = artifacts_result.scalars().all()

    report = {
        "run": {
            "id": run.id,
            "task_id": run.task_id,
            "task_name": task_name,
            "task_type": run.task_type.value,
            "status": run.status.value,
            "device_serial": run.device_serial,
            "app_package": run.app_package,
            "started_at": run.started_at.isoformat() if run.started_at else None,
            "finished_at": run.finished_at.isoformat() if run.finished_at else None,
            "duration_ms": run.duration_ms,
            "trigger_type": run.trigger_type.value,
            "summary": run.summary_json,
            "config_snapshot": run.config_snapshot,
        },
        "samples": [
            {
                "id": s.id,
                "sample_time": s.sample_time.isoformat(),
                "metric_type": s.metric_type.value,
                "metric_value": s.metric_value,
                "source": s.source,
                "extra": s.extra_json,
            }
            for s in samples
        ],
        "incidents": [
            {
                "id": i.id,
                "incident_type": i.incident_type.value,
                "event_time": i.event_time.isoformat(),
                "title": i.title,
                "detail": i.detail,
                "process_name": i.process_name,
                "thread_name": i.thread_name,
            }
            for i in incidents
        ],
        "artifacts": [
            {
                "id": a.id,
                "artifact_type": a.artifact_type.value,
                "file_name": a.file_name,
                "file_path": a.file_path,
                "file_size": a.file_size,
                "created_at": a.created_at.isoformat(),
            }
            for a in artifacts
        ],
    }

    from fastapi.responses import Response
    import json

    return Response(
        content=json.dumps(report, indent=2, ensure_ascii=False),
        media_type="application/json",
        headers={"Content-Disposition": f"attachment; filename=mobile_run_{run_id}_report.json"},
    )


# ---- Statistics ----


@router.get("/statistics/overview", response_model=dict)
@cached_json(
    key_builder=_build_mobile_stats_cache_key("overview", "project_id", "days"),
    serializer=_identity,
    deserializer=_identity,
    read_cache=_safe_get_mobile_stats_cache,
    write_cache=_safe_set_mobile_stats_cache,
)
async def get_mobile_special_overview(
    project_id: int | None = Query(None),
    days: int = Query(30, ge=1, le=365),
    db: AsyncSession = Depends(get_db),
    user=Depends(get_current_user),
):
    """Get overview statistics for mobile special testing."""
    from datetime import timedelta

    since = datetime.now(timezone.utc) - timedelta(days=days)
    since_7d = datetime.now(timezone.utc) - timedelta(days=7)

    # Total runs
    total_q = select(func.count(MobileSpecialRun.id)).where(MobileSpecialRun.created_at >= since)
    total_q = _scope_mobile_runs(total_q, user, project_id)
    total_runs = (await db.execute(total_q)).scalar() or 0

    # Completed runs
    completed_q = select(func.count(MobileSpecialRun.id)).where(
        MobileSpecialRun.created_at >= since,
        MobileSpecialRun.status == RunStatus.completed,
    )
    completed_q = _scope_mobile_runs(completed_q, user, project_id)
    completed_runs = (await db.execute(completed_q)).scalar() or 0

    # Failed runs
    failed_q = select(func.count(MobileSpecialRun.id)).where(
        MobileSpecialRun.created_at >= since,
        MobileSpecialRun.status == RunStatus.failed,
    )
    failed_q = _scope_mobile_runs(failed_q, user, project_id)
    failed_runs = (await db.execute(failed_q)).scalar() or 0

    # Running runs
    running_q = select(func.count(MobileSpecialRun.id)).where(
        MobileSpecialRun.created_at >= since,
        MobileSpecialRun.status == RunStatus.running,
    )
    running_q = _scope_mobile_runs(running_q, user, project_id)
    running_runs = (await db.execute(running_q)).scalar() or 0

    # Average duration for completed runs
    avg_dur_q = select(func.avg(MobileSpecialRun.duration_ms)).where(
        MobileSpecialRun.created_at >= since,
        MobileSpecialRun.status == RunStatus.completed,
        MobileSpecialRun.duration_ms.isnot(None),
    )
    avg_dur_q = _scope_mobile_runs(avg_dur_q, user, project_id)
    avg_duration_ms = (await db.execute(avg_dur_q)).scalar()

    # Total incidents
    incident_count_q = select(func.count(MobileIncident.id)).where(MobileIncident.event_time >= since)
    incident_count_q = incident_count_q.join(MobileSpecialRun, MobileIncident.run_id == MobileSpecialRun.id)
    incident_count_q = _scope_mobile_runs(incident_count_q, user, project_id)
    total_incidents = (await db.execute(incident_count_q)).scalar() or 0

    # Recent runs 7d
    recent_q = select(func.count(MobileSpecialRun.id)).where(
        MobileSpecialRun.created_at >= since_7d,
        MobileSpecialRun.status.in_([RunStatus.completed, RunStatus.failed]),
    )
    recent_q = _scope_mobile_runs(recent_q, user, project_id)
    recent_runs_7d = (await db.execute(recent_q)).scalar() or 0

    pass_rate = round(completed_runs / total_runs * 100, 1) if total_runs > 0 else 0.0

    result = {
        "total_runs": total_runs,
        "completed_runs": completed_runs,
        "failed_runs": failed_runs,
        "running_runs": running_runs,
        "pass_rate": pass_rate,
        "avg_duration_ms": round(float(avg_duration_ms), 0) if avg_duration_ms else None,
        "total_incidents": total_incidents,
        "recent_runs_7d": recent_runs_7d,
    }
    return result


@router.get("/statistics/trend", response_model=list[dict])
@cached_json(
    key_builder=_build_mobile_stats_cache_key("trend", "project_id", "days"),
    serializer=_identity,
    deserializer=_identity,
    read_cache=_safe_get_mobile_stats_cache,
    write_cache=_safe_set_mobile_stats_cache,
)
async def get_mobile_special_trend(
    project_id: int | None = Query(None),
    days: int = Query(30, ge=1, le=365),
    db: AsyncSession = Depends(get_db),
    user=Depends(get_current_user),
):
    """Get daily trend statistics for mobile special testing."""
    from datetime import timedelta
    from sqlalchemy import cast, Date

    since = datetime.now(timezone.utc) - timedelta(days=days)
    date_col = cast(MobileSpecialRun.created_at, Date).label("date")

    completed_filter = MobileSpecialRun.status == RunStatus.completed
    failed_filter = MobileSpecialRun.status == RunStatus.failed

    base_select = [
        date_col,
        func.count(MobileSpecialRun.id).label("total"),
        func.sum(sql_case((completed_filter, 1), else_=0)).label("completed"),
        func.sum(sql_case((failed_filter, 1), else_=0)).label("failed"),
    ]

    stmt = select(*base_select).where(MobileSpecialRun.created_at >= since).group_by(date_col).order_by(date_col)

    stmt = _scope_mobile_runs(stmt, user, project_id)

    rows = (await db.execute(stmt)).all()
    result = [
        {
            "date": str(r.date),
            "total": r.total,
            "completed": r.completed or 0,
            "failed": r.failed or 0,
            "pass_rate": round((r.completed or 0) / r.total * 100, 1) if r.total else 0.0,
        }
        for r in rows
    ]
    return result


@router.get("/statistics/task-stats", response_model=list[dict])
@cached_json(
    key_builder=_build_mobile_stats_cache_key("task-stats", "project_id", "days", "limit"),
    serializer=_identity,
    deserializer=_identity,
    read_cache=_safe_get_mobile_stats_cache,
    write_cache=_safe_set_mobile_stats_cache,
)
async def get_task_statistics(
    project_id: int | None = Query(None),
    days: int = Query(30, ge=1, le=365),
    limit: int = Query(10, ge=1, le=50),
    db: AsyncSession = Depends(get_db),
    user=Depends(get_current_user),
):
    """Get per-task statistics summary."""
    from datetime import timedelta

    since = datetime.now(timezone.utc) - timedelta(days=days)

    completed_filter = MobileSpecialRun.status == RunStatus.completed
    failed_filter = MobileSpecialRun.status == RunStatus.failed

    stmt = (
        select(
            MobileSpecialTask.id.label("task_id"),
            MobileSpecialTask.name.label("task_name"),
            MobileSpecialTask.task_type,
            func.count(MobileSpecialRun.id).label("total_runs"),
            func.sum(sql_case((completed_filter, 1), else_=0)).label("completed_runs"),
            func.sum(sql_case((failed_filter, 1), else_=0)).label("failed_runs"),
            func.max(MobileSpecialRun.created_at).label("last_run_at"),
        )
        .join(MobileSpecialRun, MobileSpecialTask.id == MobileSpecialRun.task_id)
        .where(MobileSpecialRun.created_at >= since)
        .group_by(MobileSpecialTask.id, MobileSpecialTask.name, MobileSpecialTask.task_type)
        .order_by(func.count(MobileSpecialRun.id).desc())
        .limit(limit)
    )

    stmt = scope_to_visible_projects(stmt, MobileSpecialTask.project_id, user, project_id)

    rows = (await db.execute(stmt)).all()
    result = [
        {
            "task_id": r.task_id,
            "task_name": r.task_name,
            "task_type": r.task_type.value if hasattr(r.task_type, "value") else str(r.task_type),
            "total_runs": r.total_runs,
            "completed_runs": r.completed_runs or 0,
            "failed_runs": r.failed_runs or 0,
            "pass_rate": round((r.completed_runs or 0) / r.total_runs * 100, 1) if r.total_runs else 0.0,
            "last_run_at": r.last_run_at.isoformat() if r.last_run_at else None,
        }
        for r in rows
    ]
    return result
