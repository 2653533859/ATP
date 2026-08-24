"""Project-level report center APIs."""

from __future__ import annotations

import re
from datetime import datetime, timedelta, timezone
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import Date, case as sql_case, cast, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import assert_project_access, get_current_user
from app.core.database import get_db
from app.models.case import CaseType, RunStatus, StepResult, TestCase, TestRun
from app.models.defect import Defect
from app.models.project import Module
from app.models.user import User
from app.models.user_project import ProjectRole
from app.schemas.reports import (
    ReportCompareMetric,
    ReportCompareOut,
    ReportOverviewOut,
    ReportRunItem,
    ReportRunSnapshot,
    ReportTrendItem,
)
from app.services.project_scope import scope_to_visible_projects

router = APIRouter(tags=["测试报告"])

_FINISHED_STATUSES = {RunStatus.passed, RunStatus.failed, RunStatus.error}
_ACTIVE_DEFECT_STATUSES = {"open", "in_progress", "reopened"}
_SENSITIVE_PATTERN = re.compile(
    r"(?i)(authorization|cookie|set-cookie|password|passwd|token|secret|api[_-]?key)\s*[:=]\s*(?:bearer\s+)?[^,;\n]+"
)


def _value(value: Any) -> str:
    return str(getattr(value, "value", value))


def _safe_error(value: Any, limit: int = 500) -> str | None:
    if value is None:
        return None
    text = _SENSITIVE_PATTERN.sub(lambda match: f"{match.group(1)}=[REDACTED]", str(value))
    return text[:limit]


def _since(days: int) -> datetime:
    return datetime.now(timezone.utc) - timedelta(days=days)


def _quality_score(
    pass_rate: float, coverage_rate: float, open_defects: int, total_cases: int, total_runs: int
) -> tuple[float, float]:
    """Return transparent rule-based quality score and defect health percentage."""
    if total_runs == 0:
        return 0.0, 100.0 if open_defects == 0 else 0.0
    defect_health = max(0.0, 100.0 - min(open_defects / max(total_cases, 1), 1.0) * 100.0)
    score = pass_rate * 0.6 + coverage_rate * 0.25 + defect_health * 0.15
    return round(score, 1), round(defect_health, 1)


def _project_run_query(project_id: int | None, user: User):
    stmt = select(TestRun).join(TestCase, TestRun.case_id == TestCase.id).join(Module, TestCase.module_id == Module.id)
    return scope_to_visible_projects(stmt, Module.project_id, user, project_id)


async def _ensure_project_access(db: AsyncSession, user: User, project_id: int | None) -> None:
    if project_id is not None:
        await assert_project_access(db, user, project_id, ProjectRole.viewer)


async def _load_run_snapshot(db: AsyncSession, user: User, run_id: int) -> ReportRunSnapshot:
    result = await db.execute(
        select(TestRun, TestCase.name, TestCase.case_type, Module.project_id)
        .join(TestCase, TestRun.case_id == TestCase.id)
        .join(Module, TestCase.module_id == Module.id)
        .where(TestRun.id == run_id)
    )
    row = result.one_or_none()
    if row is None:
        raise HTTPException(status_code=404, detail="执行记录不存在")
    run, case_name, case_type, project_id = row
    await assert_project_access(db, user, project_id, ProjectRole.viewer)
    if run.status not in _FINISHED_STATUSES:
        raise HTTPException(status_code=409, detail="只能对已完成的执行记录进行报告对比")
    steps_result = await db.execute(select(StepResult.status).where(StepResult.run_id == run.id))
    statuses = [_value(value) for value in steps_result.scalars().all()]
    passed_steps = statuses.count(RunStatus.passed.value)
    failed_steps = statuses.count(RunStatus.failed.value)
    error_steps = statuses.count(RunStatus.error.value)
    return ReportRunSnapshot(
        id=run.id,
        project_id=project_id,
        case_id=run.case_id,
        case_name=str(case_name),
        case_type=_value(case_type),
        status=_value(run.status),
        duration_ms=run.duration_ms,
        total_steps=len(statuses),
        passed_steps=passed_steps,
        failed_steps=failed_steps,
        error_steps=error_steps,
        error_message=_safe_error(run.error_message),
        created_at=run.created_at,
    )


def _compare_metrics(baseline: ReportRunSnapshot, current: ReportRunSnapshot) -> list[ReportCompareMetric]:
    values = (
        ("duration_ms", "执行时长", baseline.duration_ms or 0, current.duration_ms or 0, "ms"),
        ("total_steps", "步骤数", baseline.total_steps, current.total_steps, "步"),
        ("failed_steps", "失败步骤", baseline.failed_steps, current.failed_steps, "步"),
        ("error_steps", "异常步骤", baseline.error_steps, current.error_steps, "步"),
    )
    return [
        ReportCompareMetric(
            key=key,
            label=label,
            baseline=float(old),
            current=float(new),
            delta=float(new - old),
            unit=unit,
        )
        for key, label, old, new, unit in values
    ]


@router.get("/reports/overview", response_model=ReportOverviewOut)
async def get_report_overview(
    project_id: int | None = Query(default=None, ge=1),
    days: int = Query(default=30, ge=1, le=365),
    recent_limit: int = Query(default=20, ge=1, le=50),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    await _ensure_project_access(db, user, project_id)
    since = _since(days)

    case_query = scope_to_visible_projects(
        select(func.count(TestCase.id)).join(Module, TestCase.module_id == Module.id),
        Module.project_id,
        user,
        project_id,
    )
    total_cases = int((await db.execute(case_query)).scalar_one() or 0)

    run_base = _project_run_query(project_id, user).where(
        TestRun.status.in_(_FINISHED_STATUSES),
        TestRun.created_at >= since,
    )
    run_subquery = run_base.subquery("finished_runs")
    run_columns = run_subquery.c
    run_summary = await db.execute(
        select(
            func.count(run_columns.id).label("total"),
            func.sum(sql_case((run_columns.status == RunStatus.passed, 1), else_=0)).label("passed"),
            func.sum(sql_case((run_columns.status == RunStatus.failed, 1), else_=0)).label("failed"),
            func.sum(sql_case((run_columns.status == RunStatus.error, 1), else_=0)).label("error"),
            func.avg(run_columns.duration_ms).label("avg_duration"),
            func.count(func.distinct(run_columns.case_id)).label("executed_cases"),
        ).select_from(run_subquery)
    )
    summary = run_summary.one()
    total_runs = int(summary.total or 0)
    passed_runs = int(summary.passed or 0)
    failed_runs = int(summary.failed or 0)
    error_runs = int(summary.error or 0)
    executed_cases = int(summary.executed_cases or 0)
    pass_rate = round(passed_runs / total_runs * 100, 1) if total_runs else 0.0
    coverage_rate = round(executed_cases / total_cases * 100, 1) if total_cases else 0.0
    avg_duration = round(float(summary.avg_duration), 0) if summary.avg_duration is not None else None

    defect_query = select(func.count(Defect.id)).where(Defect.status.in_(_ACTIVE_DEFECT_STATUSES))
    defect_query = scope_to_visible_projects(defect_query, Defect.project_id, user, project_id)
    open_defects = int((await db.execute(defect_query)).scalar_one() or 0)
    quality_score, defect_health = _quality_score(pass_rate, coverage_rate, open_defects, total_cases, total_runs)

    date_col = cast(run_columns.created_at, Date).label("date")
    trend_query = (
        select(
            date_col,
            func.count(run_columns.id).label("total"),
            func.sum(sql_case((run_columns.status == RunStatus.passed, 1), else_=0)).label("passed"),
            func.sum(sql_case((run_columns.status == RunStatus.failed, 1), else_=0)).label("failed"),
            func.sum(sql_case((run_columns.status == RunStatus.error, 1), else_=0)).label("error"),
            func.avg(run_columns.duration_ms).label("avg_duration"),
        )
        .select_from(run_subquery)
        .group_by(date_col)
        .order_by(date_col)
    )
    trend_rows = (await db.execute(trend_query)).all()
    trend = [
        ReportTrendItem(
            date=str(row.date)[:10],
            total=int(row.total or 0),
            passed=int(row.passed or 0),
            failed=int(row.failed or 0),
            error=int(row.error or 0),
            pass_rate=round((row.passed or 0) / row.total * 100, 1) if row.total else 0.0,
            avg_duration_ms=round(float(row.avg_duration), 0) if row.avg_duration is not None else None,
        )
        for row in trend_rows
    ]

    recent_query = (
        select(TestRun, TestCase.name, TestCase.case_type, Module.project_id)
        .join(TestCase, TestRun.case_id == TestCase.id)
        .join(Module, TestCase.module_id == Module.id)
        .where(TestRun.status.in_(_FINISHED_STATUSES), TestRun.created_at >= since)
    )
    recent_query = scope_to_visible_projects(recent_query, Module.project_id, user, project_id)
    recent_rows = (await db.execute(recent_query.order_by(TestRun.created_at.desc()).limit(recent_limit))).all()
    recent_runs = [
        ReportRunItem(
            id=run.id,
            project_id=run_project_id,
            case_id=run.case_id,
            case_name=str(case_name),
            case_type=_value(case_type),
            status=_value(run.status),
            duration_ms=run.duration_ms,
            error_message=_safe_error(run.error_message),
            created_at=run.created_at,
        )
        for run, case_name, case_type, run_project_id in recent_rows
    ]

    return ReportOverviewOut(
        project_id=project_id,
        days=days,
        total_cases=total_cases,
        executed_cases=executed_cases,
        coverage_rate=coverage_rate,
        total_runs=total_runs,
        passed_runs=passed_runs,
        failed_runs=failed_runs,
        error_runs=error_runs,
        pass_rate=pass_rate,
        avg_duration_ms=avg_duration,
        open_defects=open_defects,
        defect_health_rate=defect_health,
        quality_score=quality_score,
        trend=trend,
        recent_runs=recent_runs,
    )


@router.get("/reports/compare", response_model=ReportCompareOut)
async def compare_report_runs(
    baseline_run_id: int = Query(..., ge=1),
    current_run_id: int = Query(..., ge=1),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    if baseline_run_id == current_run_id:
        raise HTTPException(status_code=422, detail="基线运行和当前运行不能相同")
    baseline = await _load_run_snapshot(db, user, baseline_run_id)
    current = await _load_run_snapshot(db, user, current_run_id)
    if baseline.project_id != current.project_id:
        raise HTTPException(status_code=400, detail="只能比较同一项目的执行记录")
    if baseline.case_id != current.case_id:
        raise HTTPException(status_code=400, detail="只能比较同一用例的执行记录")
    metrics = _compare_metrics(baseline, current)
    has_regression = (
        current.status != RunStatus.passed.value
        or current.failed_steps + current.error_steps > baseline.failed_steps + baseline.error_steps
        or (current.duration_ms or 0) > (baseline.duration_ms or 0) * 1.2
    )
    return ReportCompareOut(
        project_id=baseline.project_id,
        baseline=baseline,
        current=current,
        metrics=metrics,
        has_regression=has_regression,
    )
