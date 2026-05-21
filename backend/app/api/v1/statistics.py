from datetime import datetime, timedelta, timezone
from typing import Literal

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select, func, case as sql_case, cast, Date
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.core.cache_decorator import cached_json
from app.core.database import get_db
from app.core.redis_client import delete_json_cache_pattern, get_json_cache, set_json_cache
import logging
from app.models.case import TestCase, TestRun, RunStatus, CaseType
from app.models.plan import TestPlan, PlanRun, PlanRunStatus, TriggerType
from app.models.suite import TestSuite, SuiteRun, SuiteRunStatus
from app.models.project import Module
from app.models.user import User
from app.schemas.statistics import (
    OverviewOut,
    PassRateTrendItem,
    DurationTrendItem,
    FailureTopItem,
    ExecutorTopItem,
    TriggerTypeStatItem,
    AggregateTrendItem,
)

router = APIRouter(tags=["statistics"])
logger = logging.getLogger(__name__)

# 终态：只统计已结束的执行
_FINISHED = [RunStatus.passed, RunStatus.failed, RunStatus.error]
_PLAN_FINISHED = [PlanRunStatus.passed, PlanRunStatus.failed, PlanRunStatus.error]
_SUITE_FINISHED = [SuiteRunStatus.passed, SuiteRunStatus.failed, SuiteRunStatus.error]
_STATS_CACHE_TTL = 300


def _since(days: int) -> datetime:
    return datetime.now(timezone.utc) - timedelta(days=days)


def _cache_key(name: str, **kwargs) -> str:
    items = ":".join(f"{key}={kwargs[key]}" for key in sorted(kwargs))
    return f"atp:stats:{name}:{items}"


def _build_stats_cache_key(name: str, *fields: str):
    def builder(**kwargs) -> str:
        return _cache_key(name, **{field: kwargs.get(field) for field in fields})

    return builder


def _serialize_model(model):
    return model.model_dump()


def _deserialize_model(model_cls):
    return lambda payload: model_cls(**payload)


def _serialize_model_list(items):
    return [item.model_dump() for item in items]


def _deserialize_model_list(model_cls):
    return lambda payload: [model_cls(**item) for item in payload]


async def _safe_get_stats_cache(key: str):
    try:
        value = await get_json_cache(key)
        result = "hit" if value is not None else "miss"
        logger.debug("stats cache %s: %s", result, key)
        try:
            from app.core.metrics import STATS_CACHE

            STATS_CACHE.labels(result=result).inc()
        except Exception:
            pass
        return value
    except Exception:
        logger.exception("Failed to read statistics cache: %s", key)
        try:
            from app.core.metrics import STATS_CACHE

            STATS_CACHE.labels(result="error").inc()
        except Exception:
            pass
        return None


async def _safe_set_stats_cache(key: str, value) -> None:
    try:
        await set_json_cache(key, value, _STATS_CACHE_TTL)
        logger.debug("stats cache write: %s", key)
    except Exception:
        logger.exception("Failed to write statistics cache: %s", key)


async def invalidate_stats_cache() -> None:
    try:
        await delete_json_cache_pattern("atp:stats:*")
    except Exception:
        logger.exception("Failed to invalidate statistics cache")


def _resolve_date_col(created_at_col, aggregate: str):
    """daily → 按日 cast Date；weekly → 按周 date_trunc。返回值统一 label 为 'date'。"""
    if aggregate == "weekly":
        return func.date_trunc("week", created_at_col).label("date")
    return cast(created_at_col, Date).label("date")


def _apply_project_filter(stmt, project_id: int | None):
    if project_id is not None:
        stmt = (
            stmt
            .join(TestCase, TestRun.case_id == TestCase.id)
            .join(Module, TestCase.module_id == Module.id)
            .where(Module.project_id == project_id)
        )
    return stmt


def _apply_run_filters(stmt, project_id: int | None, case_type: CaseType | None):
    if project_id is not None or case_type is not None:
        stmt = stmt.join(TestCase, TestRun.case_id == TestCase.id)
        if project_id is not None:
            stmt = stmt.join(Module, TestCase.module_id == Module.id).where(Module.project_id == project_id)
        if case_type is not None:
            stmt = stmt.where(TestCase.case_type == case_type)
    return stmt


def _apply_plan_run_project_filter(stmt, project_id: int | None):
    if project_id is not None:
        stmt = stmt.join(TestPlan, PlanRun.plan_id == TestPlan.id).where(TestPlan.project_id == project_id)
    return stmt


def _apply_suite_run_project_filter(stmt, project_id: int | None):
    if project_id is not None:
        stmt = stmt.join(TestSuite, SuiteRun.suite_id == TestSuite.id).where(TestSuite.project_id == project_id)
    return stmt


# ── 总览 ────────────────────────────────────────────────
@router.get("/statistics/overview", response_model=OverviewOut)
@cached_json(
    key_builder=_build_stats_cache_key("overview", "project_id", "days"),
    serializer=_serialize_model,
    deserializer=_deserialize_model(OverviewOut),
    read_cache=_safe_get_stats_cache,
    write_cache=_safe_set_stats_cache,
)
async def get_overview(
    project_id: int | None = Query(None),
    days: int = Query(30, ge=1, le=365),
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_user),
):
    case_q = select(func.count(TestCase.id))
    if project_id is not None:
        case_q = (
            case_q
            .join(Module, TestCase.module_id == Module.id)
            .where(Module.project_id == project_id)
        )
    total_cases = (await db.execute(case_q)).scalar() or 0

    since = _since(days)

    run_q = select(
        func.count(TestRun.id),
        func.sum(sql_case((TestRun.status == RunStatus.passed, 1), else_=0)),
    ).where(TestRun.status.in_(_FINISHED), TestRun.created_at >= since)
    run_q = _apply_project_filter(run_q, project_id)
    row = (await db.execute(run_q)).one()
    total_runs = row[0] or 0
    total_passed = row[1] or 0
    pass_rate = round(total_passed / total_runs * 100, 1) if total_runs else 0.0

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
@cached_json(
    key_builder=_build_stats_cache_key("pass-rate-trend", "project_id", "days", "case_type", "aggregate"),
    serializer=_serialize_model_list,
    deserializer=_deserialize_model_list(PassRateTrendItem),
    read_cache=_safe_get_stats_cache,
    write_cache=_safe_set_stats_cache,
)
async def get_pass_rate_trend(
    project_id: int | None = Query(None),
    days: int = Query(30, ge=1, le=365),
    case_type: CaseType | None = Query(None),
    aggregate: Literal["daily", "weekly"] = Query("daily"),
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_user),
):
    since = _since(days)
    date_col = _resolve_date_col(TestRun.created_at, aggregate)

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
            date=str(r.date)[:10],
            total=r.total,
            passed=r.passed,
            rate=round(r.passed / r.total * 100, 1) if r.total else 0.0,
        )
        for r in rows
    ]


# ── 执行时长趋势 ────────────────────────────────────────
@router.get("/statistics/duration-trend", response_model=list[DurationTrendItem])
@cached_json(
    key_builder=_build_stats_cache_key("duration-trend", "project_id", "days", "case_type", "aggregate"),
    serializer=_serialize_model_list,
    deserializer=_deserialize_model_list(DurationTrendItem),
    read_cache=_safe_get_stats_cache,
    write_cache=_safe_set_stats_cache,
)
async def get_duration_trend(
    project_id: int | None = Query(None),
    days: int = Query(30, ge=1, le=365),
    case_type: CaseType | None = Query(None),
    aggregate: Literal["daily", "weekly"] = Query("daily"),
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_user),
):
    since = _since(days)
    date_col = _resolve_date_col(TestRun.created_at, aggregate)

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
            date=str(r.date)[:10],
            avg_duration_ms=round(float(r.avg_ms), 0),
            max_duration_ms=int(r.max_ms),
            run_count=r.cnt,
        )
        for r in rows
    ]


# ── 失败 Top N ──────────────────────────────────────────
@router.get("/statistics/failure-top", response_model=list[FailureTopItem])
@cached_json(
    key_builder=_build_stats_cache_key("failure-top", "project_id", "days", "top", "case_type"),
    serializer=_serialize_model_list,
    deserializer=_deserialize_model_list(FailureTopItem),
    read_cache=_safe_get_stats_cache,
    write_cache=_safe_set_stats_cache,
)
async def get_failure_top(
    project_id: int | None = Query(None),
    days: int = Query(30, ge=1, le=365),
    top: int = Query(10, ge=1, le=50),
    case_type: CaseType | None = Query(None),
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
    if case_type is not None:
        stmt = stmt.where(TestCase.case_type == case_type)

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


@router.get("/statistics/executor-top", response_model=list[ExecutorTopItem])
@cached_json(
    key_builder=_build_stats_cache_key("executor-top", "project_id", "days", "top", "case_type"),
    serializer=_serialize_model_list,
    deserializer=_deserialize_model_list(ExecutorTopItem),
    read_cache=_safe_get_stats_cache,
    write_cache=_safe_set_stats_cache,
)
async def get_executor_top(
    project_id: int | None = Query(None),
    days: int = Query(30, ge=1, le=365),
    top: int = Query(10, ge=1, le=50),
    case_type: CaseType | None = Query(None),
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_user),
):
    since = _since(days)
    run_count = func.count(TestRun.id).label("run_count")
    stmt = (
        select(
            User.id.label("user_id"),
            User.username.label("username"),
            run_count,
        )
        .join(User, TestRun.triggered_by == User.id)
        .where(TestRun.status.in_(_FINISHED), TestRun.created_at >= since)
        .group_by(User.id, User.username)
        .order_by(run_count.desc(), User.id.asc())
        .limit(top)
    )
    stmt = _apply_run_filters(stmt, project_id, case_type)

    rows = (await db.execute(stmt)).all()
    return [
        ExecutorTopItem(
            user_id=r.user_id,
            username=r.username,
            run_count=r.run_count,
        )
        for r in rows
    ]


@router.get("/statistics/trigger-type-stats", response_model=list[TriggerTypeStatItem])
@cached_json(
    key_builder=_build_stats_cache_key("trigger-type-stats", "project_id", "days"),
    serializer=_serialize_model_list,
    deserializer=_deserialize_model_list(TriggerTypeStatItem),
    read_cache=_safe_get_stats_cache,
    write_cache=_safe_set_stats_cache,
)
async def get_trigger_type_stats(
    project_id: int | None = Query(None),
    days: int = Query(30, ge=1, le=365),
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_user),
):
    since = _since(days)
    stmt = (
        select(
            PlanRun.trigger_type.label("trigger_type"),
            func.count(PlanRun.id).label("count"),
        )
        .where(PlanRun.status.in_(_PLAN_FINISHED), PlanRun.created_at >= since)
        .group_by(PlanRun.trigger_type)
        .order_by(func.count(PlanRun.id).desc())
    )
    stmt = _apply_plan_run_project_filter(stmt, project_id)

    rows = (await db.execute(stmt)).all()
    return [
        TriggerTypeStatItem(
            trigger_type=r.trigger_type.value if hasattr(r.trigger_type, "value") else str(r.trigger_type),
            count=r.count,
        )
        for r in rows
    ]


@router.get("/statistics/plan-trend", response_model=list[AggregateTrendItem])
@cached_json(
    key_builder=_build_stats_cache_key("plan-trend", "project_id", "days", "aggregate"),
    serializer=_serialize_model_list,
    deserializer=_deserialize_model_list(AggregateTrendItem),
    read_cache=_safe_get_stats_cache,
    write_cache=_safe_set_stats_cache,
)
async def get_plan_trend(
    project_id: int | None = Query(None),
    days: int = Query(30, ge=1, le=365),
    aggregate: Literal["daily", "weekly"] = Query("daily"),
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_user),
):
    since = _since(days)
    date_col = _resolve_date_col(PlanRun.created_at, aggregate)
    stmt = (
        select(
            date_col,
            func.count(PlanRun.id).label("total"),
            func.sum(sql_case((PlanRun.status == PlanRunStatus.passed, 1), else_=0)).label("passed"),
        )
        .where(PlanRun.status.in_(_PLAN_FINISHED), PlanRun.created_at >= since)
        .group_by(date_col)
        .order_by(date_col)
    )
    stmt = _apply_plan_run_project_filter(stmt, project_id)

    rows = (await db.execute(stmt)).all()
    return [
        AggregateTrendItem(
            date=str(r.date)[:10],
            total=r.total,
            passed=r.passed or 0,
            rate=round((r.passed or 0) / r.total * 100, 1) if r.total else 0.0,
        )
        for r in rows
    ]


@router.get("/statistics/suite-trend", response_model=list[AggregateTrendItem])
@cached_json(
    key_builder=_build_stats_cache_key("suite-trend", "project_id", "days", "aggregate"),
    serializer=_serialize_model_list,
    deserializer=_deserialize_model_list(AggregateTrendItem),
    read_cache=_safe_get_stats_cache,
    write_cache=_safe_set_stats_cache,
)
async def get_suite_trend(
    project_id: int | None = Query(None),
    days: int = Query(30, ge=1, le=365),
    aggregate: Literal["daily", "weekly"] = Query("daily"),
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_user),
):
    since = _since(days)
    date_col = _resolve_date_col(SuiteRun.created_at, aggregate)
    stmt = (
        select(
            date_col,
            func.count(SuiteRun.id).label("total"),
            func.sum(sql_case((SuiteRun.status == SuiteRunStatus.passed, 1), else_=0)).label("passed"),
        )
        .where(SuiteRun.status.in_(_SUITE_FINISHED), SuiteRun.created_at >= since)
        .group_by(date_col)
        .order_by(date_col)
    )
    stmt = _apply_suite_run_project_filter(stmt, project_id)

    rows = (await db.execute(stmt)).all()
    return [
        AggregateTrendItem(
            date=str(r.date)[:10],
            total=r.total,
            passed=r.passed or 0,
            rate=round((r.passed or 0) / r.total * 100, 1) if r.total else 0.0,
        )
        for r in rows
    ]
