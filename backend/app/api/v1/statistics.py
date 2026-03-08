from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select, func, case as sql_case, cast, Date
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.core.database import get_db
from app.models.case import TestCase, TestRun, RunStatus, CaseType
from app.models.project import Module
from app.models.user import User
from app.schemas.statistics import (
    OverviewOut,
    PassRateTrendItem,
    DurationTrendItem,
    FailureTopItem,
)

router = APIRouter(tags=["statistics"])

# 终态：只统计已结束的执行
_FINISHED = [RunStatus.passed, RunStatus.failed, RunStatus.error]


def _since(days: int) -> datetime:
    return datetime.now(timezone.utc) - timedelta(days=days)


def _apply_project_filter(stmt, project_id: int | None):
    """按 project_id 过滤：TestRun → TestCase → Module → project_id（显式 JOIN）"""
    if project_id is not None:
        stmt = (
            stmt
            .join(TestCase, TestRun.case_id == TestCase.id)
            .join(Module, TestCase.module_id == Module.id)
            .where(Module.project_id == project_id)
        )
    return stmt


def _apply_run_filters(stmt, project_id: int | None, case_type: CaseType | None):
    """为基于 TestRun 的查询附加 project / case_type 过滤（显式 JOIN）"""
    if project_id is not None or case_type is not None:
        stmt = stmt.join(TestCase, TestRun.case_id == TestCase.id)
        if project_id is not None:
            stmt = stmt.join(Module, TestCase.module_id == Module.id).where(Module.project_id == project_id)
        if case_type is not None:
            stmt = stmt.where(TestCase.case_type == case_type)
    return stmt


# ── 总览 ────────────────────────────────────────────────
@router.get("/statistics/overview", response_model=OverviewOut)
async def get_overview(
    project_id: int | None = Query(None),
    days: int = Query(30, ge=1, le=365),
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_user),
):
    # 总用例数
    case_q = select(func.count(TestCase.id))
    if project_id is not None:
        case_q = (
            case_q
            .join(Module, TestCase.module_id == Module.id)
            .where(Module.project_id == project_id)
        )
    total_cases = (await db.execute(case_q)).scalar() or 0

    since = _since(days)

    # 总执行次数 & 通过率
    run_q = select(
        func.count(TestRun.id),
        func.sum(sql_case((TestRun.status == RunStatus.passed, 1), else_=0)),
    ).where(TestRun.status.in_(_FINISHED), TestRun.created_at >= since)
    run_q = _apply_project_filter(run_q, project_id)
    row = (await db.execute(run_q)).one()
    total_runs = row[0] or 0
    total_passed = row[1] or 0
    pass_rate = round(total_passed / total_runs * 100, 1) if total_runs else 0.0

    # 近 7 日执行次数
    recent_q = select(func.count(TestRun.id)).where(
        TestRun.status.in_(_FINISHED),
        TestRun.created_at >= _since(7),
    )
    recent_q = _apply_project_filter(recent_q, project_id)
    recent_runs_7d = (await db.execute(recent_q)).scalar() or 0

    return OverviewOut(
        total_cases=total_cases,
        total_runs=total_runs,
        pass_rate=pass_rate,
        recent_runs_7d=recent_runs_7d,
    )


# ── 通过率趋势 ──────────────────────────────────────────
@router.get("/statistics/pass-rate-trend", response_model=list[PassRateTrendItem])
async def get_pass_rate_trend(
    project_id: int | None = Query(None),
    days: int = Query(30, ge=1, le=365),
    case_type: CaseType | None = Query(None),
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_user),
):
    since = _since(days)
    date_col = cast(TestRun.created_at, Date).label("date")

    stmt = (
        select(
            date_col,
            func.count(TestRun.id).label("total"),
            func.sum(sql_case((TestRun.status == RunStatus.passed, 1), else_=0)).label("passed"),
        )
        .where(TestRun.status.in_(_FINISHED), TestRun.created_at >= since)
        .group_by(date_col)
        .order_by(date_col)
    )

    stmt = _apply_run_filters(stmt, project_id, case_type)

    rows = (await db.execute(stmt)).all()
    return [
        PassRateTrendItem(
            date=str(r.date),
            total=r.total,
            passed=r.passed,
            rate=round(r.passed / r.total * 100, 1) if r.total else 0.0,
        )
        for r in rows
    ]


# ── 执行时长趋势 ────────────────────────────────────────
@router.get("/statistics/duration-trend", response_model=list[DurationTrendItem])
async def get_duration_trend(
    project_id: int | None = Query(None),
    days: int = Query(30, ge=1, le=365),
    case_type: CaseType | None = Query(None),
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_user),
):
    since = _since(days)
    date_col = cast(TestRun.created_at, Date).label("date")

    stmt = (
        select(
            date_col,
            func.avg(TestRun.duration_ms).label("avg_ms"),
            func.max(TestRun.duration_ms).label("max_ms"),
            func.count(TestRun.id).label("cnt"),
        )
        .where(
            TestRun.status.in_(_FINISHED),
            TestRun.created_at >= since,
            TestRun.duration_ms.isnot(None),
        )
        .group_by(date_col)
        .order_by(date_col)
    )

    stmt = _apply_run_filters(stmt, project_id, case_type)

    rows = (await db.execute(stmt)).all()
    return [
        DurationTrendItem(
            date=str(r.date),
            avg_duration_ms=round(float(r.avg_ms), 0),
            max_duration_ms=int(r.max_ms),
            run_count=r.cnt,
        )
        for r in rows
    ]


# ── 失败 Top N ──────────────────────────────────────────
@router.get("/statistics/failure-top", response_model=list[FailureTopItem])
async def get_failure_top(
    project_id: int | None = Query(None),
    days: int = Query(30, ge=1, le=365),
    top: int = Query(10, ge=1, le=50),
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_user),
):
    since = _since(days)
    fail_count = func.count(TestRun.id).label("failure_count")

    stmt = (
        select(
            TestCase.id.label("case_id"),
            Module.project_id.label("project_id"),
            TestCase.module_id.label("module_id"),
            TestCase.name.label("case_name"),
            TestCase.case_type.label("case_type"),
            fail_count,
        )
        .join(TestCase, TestRun.case_id == TestCase.id)
        .join(Module, TestCase.module_id == Module.id)
        .where(
            TestRun.status.in_([RunStatus.failed, RunStatus.error]),
            TestRun.created_at >= since,
        )
        .group_by(TestCase.id, Module.project_id, TestCase.module_id, TestCase.name, TestCase.case_type)
        .order_by(fail_count.desc())
        .limit(top)
    )

    if project_id is not None:
        stmt = stmt.where(Module.project_id == project_id)

    rows = (await db.execute(stmt)).all()
    return [
        FailureTopItem(
            case_id=r.case_id,
            project_id=r.project_id,
            module_id=r.module_id,
            case_name=r.case_name,
            case_type=r.case_type.value if hasattr(r.case_type, "value") else str(r.case_type),
            failure_count=r.failure_count,
        )
        for r in rows
    ]
