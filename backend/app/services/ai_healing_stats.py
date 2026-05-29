from __future__ import annotations

from datetime import datetime, timedelta, timezone

from sqlalchemy import Date, case as sql_case, cast, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.case import StepResult, TestCase, TestRun
from app.models.healing_feedback import HealingFeedbackAggregate
from app.models.healing_prompt_example import HealingPromptExample
from app.services.healing_feedback import build_error_fingerprint
from app.schemas.ai_healing_stats import (
    AIHealingCaseTypeStat,
    AIHealingProductionFeedback,
    AIHealingStatsOut,
    AIHealingTopFingerprint,
    AIHealingTrendItem,
)


def _rate(adopted: int, total: int) -> float:
    return round((adopted / total) * 100, 2) if total > 0 else 0.0


def _date_key(value) -> str:
    if hasattr(value, "isoformat"):
        return value.isoformat()
    return str(value)


def _is_ai_healing_regression(run: TestRun) -> bool:
    return isinstance(run.result_summary, dict) and run.result_summary.get("triggered_by_ai_healing_patch") is True


def _is_success_status(status) -> bool:
    value = status.value if hasattr(status, "value") else str(status)
    return value in {"passed", "success"}


async def build_ai_healing_stats(db: AsyncSession, *, days: int = 30) -> AIHealingStatsOut:
    since = datetime.now(timezone.utc) - timedelta(days=days)

    total_result = await db.execute(
        select(
            func.count(StepResult.id),
            func.sum(sql_case((StepResult.healing_feedback == "adopted", 1), else_=0)),
            func.sum(sql_case((StepResult.healing_feedback == "rejected", 1), else_=0)),
        ).where(
            StepResult.healing_feedback.in_(["adopted", "rejected"]),
            StepResult.healing_feedback_at.is_not(None),
            StepResult.healing_feedback_at >= since,
        )
    )
    total_count, adopted_count, rejected_count = total_result.one()
    total_count = int(total_count or 0)
    adopted_count = int(adopted_count or 0)
    rejected_count = int(rejected_count or 0)

    by_case_result = await db.execute(
        select(
            TestCase.case_type,
            func.count(StepResult.id),
            func.sum(sql_case((StepResult.healing_feedback == "adopted", 1), else_=0)),
            func.sum(sql_case((StepResult.healing_feedback == "rejected", 1), else_=0)),
        )
        .join(TestRun, StepResult.run_id == TestRun.id)
        .join(TestCase, TestRun.case_id == TestCase.id)
        .where(
            StepResult.healing_feedback.in_(["adopted", "rejected"]),
            StepResult.healing_feedback_at.is_not(None),
            StepResult.healing_feedback_at >= since,
        )
        .group_by(TestCase.case_type)
    )
    by_case_type: list[AIHealingCaseTypeStat] = []
    for case_type_value, total, adopted, rejected in by_case_result.all():
        case_type = case_type_value.value if hasattr(case_type_value, "value") else str(case_type_value)
        total_i = int(total or 0)
        adopted_i = int(adopted or 0)
        rejected_i = int(rejected or 0)
        by_case_type.append(
            AIHealingCaseTypeStat(
                case_type=case_type,
                total_count=total_i,
                adopted_count=adopted_i,
                rejected_count=rejected_i,
                adopted_rate=_rate(adopted_i, total_i),
            )
        )

    top_rows_result = await db.execute(
        select(StepResult, TestCase.case_type)
        .join(TestRun, StepResult.run_id == TestRun.id)
        .join(TestCase, TestRun.case_id == TestCase.id)
        .where(
            StepResult.healing_feedback.in_(["adopted", "rejected"]),
            StepResult.healing_feedback_at.is_not(None),
            StepResult.healing_feedback_at >= since,
        )
    )
    fingerprint_buckets: dict[tuple[str, str], dict[str, int]] = {}
    for step, case_type_value in top_rows_result.all():
        case_type = case_type_value.value if hasattr(case_type_value, "value") else str(case_type_value)
        response_status = None
        if isinstance(step.response_data, dict):
            response_status = step.response_data.get("status_code")
        fingerprint = build_error_fingerprint(
            case_type=case_type,
            step_name=step.name,
            error_message=step.error_message,
            response_status_code=response_status,
        )
        bucket = fingerprint_buckets.setdefault((fingerprint, case_type), {"adopted": 0, "rejected": 0})
        if step.healing_feedback == "adopted":
            bucket["adopted"] += 1
        elif step.healing_feedback == "rejected":
            bucket["rejected"] += 1

    top_error_fingerprints = []
    for (fingerprint, case_type), counts in fingerprint_buckets.items():
        adopted_i = counts["adopted"]
        rejected_i = counts["rejected"]
        total_i = adopted_i + rejected_i
        top_error_fingerprints.append(
            AIHealingTopFingerprint(
                error_fingerprint=fingerprint,
                case_type=case_type,
                total_count=total_i,
                adopted_count=adopted_i,
                rejected_count=rejected_i,
                adopted_rate=_rate(adopted_i, total_i),
            )
        )
    top_error_fingerprints.sort(key=lambda item: (item.total_count, item.adopted_rate), reverse=True)
    top_error_fingerprints = top_error_fingerprints[:10]

    trend_result = await db.execute(
        select(
            cast(StepResult.healing_feedback_at, Date).label("feedback_date"),
            func.count(StepResult.id),
            func.sum(sql_case((StepResult.healing_feedback == "adopted", 1), else_=0)),
            func.sum(sql_case((StepResult.healing_feedback == "rejected", 1), else_=0)),
        )
        .where(
            StepResult.healing_feedback.in_(["adopted", "rejected"]),
            StepResult.healing_feedback_at >= since,
        )
        .group_by("feedback_date")
        .order_by("feedback_date")
    )
    recent_trend: list[AIHealingTrendItem] = []
    for day, total, adopted, rejected in trend_result.all():
        total_i = int(total or 0)
        adopted_i = int(adopted or 0)
        rejected_i = int(rejected or 0)
        recent_trend.append(
            AIHealingTrendItem(
                date=_date_key(day),
                total_count=total_i,
                adopted_count=adopted_i,
                rejected_count=rejected_i,
                adopted_rate=_rate(adopted_i, total_i),
            )
        )

    example_result = await db.execute(
        select(func.count(HealingPromptExample.id)).where(HealingPromptExample.marked_high_quality.is_(True))
    )
    high_quality_example_count = int(example_result.scalar_one() or 0)

    regression_result = await db.execute(
        select(TestRun).where(
            TestRun.created_at >= since,
            TestRun.result_summary.is_not(None),
        )
    )
    regression_runs = [run for run in regression_result.scalars().all() if _is_ai_healing_regression(run)]
    regression_triggered_count = len(regression_runs)
    regression_success_count = sum(1 for run in regression_runs if _is_success_status(run.status))

    aggregate_result = await db.execute(select(func.max(HealingFeedbackAggregate.last_aggregated_at)))
    latest_feedback_aggregated_at = aggregate_result.scalar_one_or_none()

    return AIHealingStatsOut(
        total_feedback_count=total_count,
        adopted_count=adopted_count,
        rejected_count=rejected_count,
        adopted_rate=_rate(adopted_count, total_count),
        high_quality_example_count=high_quality_example_count,
        by_case_type=by_case_type,
        top_error_fingerprints=top_error_fingerprints,
        recent_trend=recent_trend,
        production_feedback=AIHealingProductionFeedback(
            regression_triggered_count=regression_triggered_count,
            regression_success_count=regression_success_count,
            regression_success_rate=_rate(regression_success_count, regression_triggered_count),
            latest_feedback_aggregated_at=(
                latest_feedback_aggregated_at.isoformat() if latest_feedback_aggregated_at else None
            ),
        ),
    )
