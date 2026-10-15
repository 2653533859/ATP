"""Project-Level Concurrency Quota and Execution Duration Hard Limit Service (Q4.1).

Provides:
1. Multi-tenant project resource quota configuration (max concurrency, daily execution duration, single-run hard timeout).
2. Real-time active run counting across test suites, test plans, and performance tests.
3. Daily cumulative runtime calculation and limit enforcement (reject or queue).
4. Long-running zombie execution hard timeout detection and automatic abort reaper.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime, timezone
import logging
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.performance import PerformanceRun
from app.models.plan import PlanRun, PlanRunStatus, TestPlan
from app.models.project_quota import ProjectQuota
from app.models.suite import SuiteRun, SuiteRunStatus, TestSuite

logger = logging.getLogger(__name__)

DEFAULT_MAX_CONCURRENT_RUNS = 5
DEFAULT_DAILY_DURATION_LIMIT_SECONDS = 28800  # 8 hours
DEFAULT_MAX_SINGLE_RUN_TIMEOUT_SECONDS = 3600  # 1 hour
DEFAULT_OVER_QUOTA_POLICY = "reject"


@dataclass
class QuotaEvaluation:
    allowed: bool
    should_queue: bool = False
    reason: str = "within_quota"
    current_active_runs: int = 0
    max_concurrent_runs: int = DEFAULT_MAX_CONCURRENT_RUNS
    daily_duration_seconds: float = 0.0
    daily_duration_limit_seconds: int = DEFAULT_DAILY_DURATION_LIMIT_SECONDS
    policy: str = DEFAULT_OVER_QUOTA_POLICY
    details: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "allowed": self.allowed,
            "should_queue": self.should_queue,
            "reason": self.reason,
            "current_active_runs": self.current_active_runs,
            "max_concurrent_runs": self.max_concurrent_runs,
            "daily_duration_seconds": round(self.daily_duration_seconds, 1),
            "daily_duration_limit_seconds": self.daily_duration_limit_seconds,
            "policy": self.policy,
            "details": self.details,
        }


async def get_or_default_project_quota(db: AsyncSession, project_id: int) -> ProjectQuota:
    """Retrieve existing project quota or instantiate default quota instance."""
    q = select(ProjectQuota).where(ProjectQuota.project_id == project_id)
    result = await db.execute(q)
    quota = result.scalar_one_or_none()
    if quota is not None:
        return quota

    return ProjectQuota(
        project_id=project_id,
        max_concurrent_runs=DEFAULT_MAX_CONCURRENT_RUNS,
        daily_duration_limit_seconds=DEFAULT_DAILY_DURATION_LIMIT_SECONDS,
        max_single_run_timeout_seconds=DEFAULT_MAX_SINGLE_RUN_TIMEOUT_SECONDS,
        over_quota_policy=DEFAULT_OVER_QUOTA_POLICY,
        is_enabled=True,
    )


async def upsert_project_quota(
    db: AsyncSession,
    project_id: int,
    *,
    max_concurrent_runs: int | None = None,
    daily_duration_limit_seconds: int | None = None,
    max_single_run_timeout_seconds: int | None = None,
    over_quota_policy: str | None = None,
    is_enabled: bool | None = None,
    description: str | None = None,
) -> ProjectQuota:
    """Create or update a project's resource quota configuration."""
    q = select(ProjectQuota).where(ProjectQuota.project_id == project_id)
    quota = (await db.execute(q)).scalar_one_or_none()
    if quota is None:
        quota = ProjectQuota(project_id=project_id)
        db.add(quota)

    if max_concurrent_runs is not None:
        if max_concurrent_runs < 1:
            raise ValueError("最大并发任务数必须大于等于 1")
        quota.max_concurrent_runs = max_concurrent_runs

    if daily_duration_limit_seconds is not None:
        if daily_duration_limit_seconds < 60:
            raise ValueError("每日执行总时长上限不能少于 60 秒")
        quota.daily_duration_limit_seconds = daily_duration_limit_seconds

    if max_single_run_timeout_seconds is not None:
        if max_single_run_timeout_seconds < 10:
            raise ValueError("单任务硬超时时间不能少于 10 秒")
        quota.max_single_run_timeout_seconds = max_single_run_timeout_seconds

    if over_quota_policy is not None:
        if over_quota_policy not in {"reject", "queue"}:
            raise ValueError("超额策略必须为 'reject' 或 'queue'")
        quota.over_quota_policy = over_quota_policy

    if is_enabled is not None:
        quota.is_enabled = is_enabled

    if description is not None:
        quota.description = description

    await db.commit()
    await db.refresh(quota)
    return quota


async def count_project_active_runs(db: AsyncSession, project_id: int) -> int:
    """Count running and pending executions for a project across test suites, test plans, and performance runs."""
    # 1. Suite runs (joined via TestSuite)
    q_suite = (
        select(func.count(SuiteRun.id))
        .join(TestSuite, SuiteRun.suite_id == TestSuite.id)
        .where(
            TestSuite.project_id == project_id,
            SuiteRun.status.in_([SuiteRunStatus.running, SuiteRunStatus.pending]),
        )
    )
    suite_active = (await db.execute(q_suite)).scalar() or 0

    # 2. Plan runs (joined via TestPlan)
    q_plan = (
        select(func.count(PlanRun.id))
        .join(TestPlan, PlanRun.plan_id == TestPlan.id)
        .where(
            TestPlan.project_id == project_id,
            PlanRun.status.in_([PlanRunStatus.running, PlanRunStatus.pending]),
        )
    )
    plan_active = (await db.execute(q_plan)).scalar() or 0

    # 3. Performance runs
    q_perf = select(func.count(PerformanceRun.id)).where(
        PerformanceRun.project_id == project_id,
        PerformanceRun.status.in_(["running", "pending"]),
    )
    perf_active = (await db.execute(q_perf)).scalar() or 0

    return int(suite_active + plan_active + perf_active)


async def calculate_project_daily_duration_seconds(
    db: AsyncSession,
    project_id: int,
    target_date: date | None = None,
) -> float:
    """Calculate cumulative execution seconds consumed by project runs on target date (UTC)."""
    check_date = target_date or datetime.now(timezone.utc).date()
    start_of_day = datetime(check_date.year, check_date.month, check_date.day, tzinfo=timezone.utc)

    # 1. Query duration from suite runs on target date
    q_suite_dur = (
        select(func.coalesce(func.sum(SuiteRun.duration_ms), 0))
        .join(TestSuite, SuiteRun.suite_id == TestSuite.id)
        .where(
            TestSuite.project_id == project_id,
            SuiteRun.created_at >= start_of_day,
        )
    )
    suite_ms = (await db.execute(q_suite_dur)).scalar() or 0

    # 2. Query duration from plan runs
    q_plan_dur = (
        select(func.coalesce(func.sum(PlanRun.duration_ms), 0))
        .join(TestPlan, PlanRun.plan_id == TestPlan.id)
        .where(
            TestPlan.project_id == project_id,
            PlanRun.created_at >= start_of_day,
        )
    )
    plan_ms = (await db.execute(q_plan_dur)).scalar() or 0

    total_seconds = float(suite_ms + plan_ms) / 1000.0
    return round(total_seconds, 2)


async def evaluate_project_dispatch_quota(
    db: AsyncSession,
    project_id: int,
) -> QuotaEvaluation:
    """Evaluate whether a new test execution is allowed to start under project concurrency & duration limits."""
    quota = await get_or_default_project_quota(db, project_id)

    if not quota.is_enabled:
        return QuotaEvaluation(
            allowed=True,
            reason="quota_disabled",
            max_concurrent_runs=quota.max_concurrent_runs,
            daily_duration_limit_seconds=quota.daily_duration_limit_seconds,
            policy=quota.over_quota_policy,
        )

    # 1. Check Concurrency Limit
    active_count = await count_project_active_runs(db, project_id)
    if active_count >= quota.max_concurrent_runs:
        if quota.over_quota_policy == "queue":
            return QuotaEvaluation(
                allowed=True,
                should_queue=True,
                reason="concurrency_quota_queued",
                current_active_runs=active_count,
                max_concurrent_runs=quota.max_concurrent_runs,
                policy="queue",
                details={
                    "message": f"当前项目并发运行数已达上限 ({active_count}/{quota.max_concurrent_runs})，任务已自动加入排队队列"
                },
            )
        else:
            return QuotaEvaluation(
                allowed=False,
                should_queue=False,
                reason="concurrency_quota_exceeded",
                current_active_runs=active_count,
                max_concurrent_runs=quota.max_concurrent_runs,
                policy="reject",
                details={
                    "message": f"当前项目并发运行数已达上限 ({active_count}/{quota.max_concurrent_runs})，请等待正在运行的任务完成"
                },
            )

    # 2. Check Daily Cumulative Duration Limit
    daily_duration = await calculate_project_daily_duration_seconds(db, project_id)
    if daily_duration >= float(quota.daily_duration_limit_seconds):
        return QuotaEvaluation(
            allowed=False,
            should_queue=False,
            reason="daily_duration_limit_exceeded",
            current_active_runs=active_count,
            max_concurrent_runs=quota.max_concurrent_runs,
            daily_duration_seconds=daily_duration,
            daily_duration_limit_seconds=quota.daily_duration_limit_seconds,
            policy="reject",
            details={
                "message": (
                    f"当前项目今日执行时长已达上限 ({int(daily_duration)}s / {quota.daily_duration_limit_seconds}s)，"
                    "资源配额耗尽，今日拒绝调度新任务"
                )
            },
        )

    return QuotaEvaluation(
        allowed=True,
        should_queue=False,
        reason="within_quota",
        current_active_runs=active_count,
        max_concurrent_runs=quota.max_concurrent_runs,
        daily_duration_seconds=daily_duration,
        daily_duration_limit_seconds=quota.daily_duration_limit_seconds,
        policy=quota.over_quota_policy,
    )


def is_run_timed_out(
    started_at: datetime | None,
    max_timeout_seconds: int,
    now: datetime | None = None,
) -> bool:
    """Check if a running task has exceeded its execution hard timeout limit."""
    if started_at is None:
        return False
    ref_time = now or datetime.now(timezone.utc)
    if started_at.tzinfo is None:
        started_at = started_at.replace(tzinfo=timezone.utc)
    elapsed = (ref_time - started_at).total_seconds()
    return elapsed >= float(max_timeout_seconds)


async def scan_and_reap_timed_out_runs(
    db: AsyncSession,
    project_id: int | None = None,
    now: datetime | None = None,
) -> list[dict[str, Any]]:
    """Scan and abort zombie runs that have exceeded project-level hard execution timeouts."""
    ref_time = now or datetime.now(timezone.utc)
    reaped: list[dict[str, Any]] = []

    # 1. Query running suite runs
    q = (
        select(SuiteRun, TestSuite.project_id)
        .join(TestSuite, SuiteRun.suite_id == TestSuite.id)
        .where(SuiteRun.status == SuiteRunStatus.running)
    )
    if project_id is not None:
        q = q.where(TestSuite.project_id == project_id)

    rows = (await db.execute(q)).all()

    for s_run, p_id in rows:
        quota = await get_or_default_project_quota(db, p_id)
        if quota.is_enabled and is_run_timed_out(s_run.created_at, quota.max_single_run_timeout_seconds, now=ref_time):
            s_run.status = SuiteRunStatus.error
            s_run.error_message = f"执行硬超时（单任务超过上限 {quota.max_single_run_timeout_seconds} 秒）"
            s_run.cancel_requested_at = ref_time
            reaped.append(
                {
                    "run_type": "suite_run",
                    "run_id": s_run.id,
                    "project_id": p_id,
                    "created_at": s_run.created_at.isoformat() if s_run.created_at else None,
                    "timeout_limit_seconds": quota.max_single_run_timeout_seconds,
                    "reason": "execution_hard_timeout_exceeded",
                }
            )

    if reaped:
        await db.commit()

    return reaped
