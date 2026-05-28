from __future__ import annotations

import hashlib
from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Iterable

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.case import StepResult, TestCase, TestRun
from app.models.healing_feedback import HealingFeedbackAggregate


@dataclass(frozen=True)
class FeedbackRow:
    case_type: str
    step_name: str
    error_message: str | None
    response_status_code: int | str | None
    feedback: str


@dataclass(frozen=True)
class FeedbackSummary:
    error_fingerprint: str
    case_type: str
    total_count: int
    adopted_count: int
    rejected_count: int
    adopted_rate: float


def build_error_fingerprint(
    *,
    case_type: str,
    step_name: str,
    error_message: str | None,
    response_status_code: int | str | None = None,
) -> str:
    parts = [
        case_type or "",
        step_name or "",
        (error_message or "")[:500],
        str(response_status_code if response_status_code is not None else ""),
    ]
    return hashlib.sha256("\x1f".join(parts).encode("utf-8", errors="replace")).hexdigest()[:32]


def summarize_feedback_rows(rows: Iterable[FeedbackRow]) -> list[FeedbackSummary]:
    buckets: dict[tuple[str, str], dict[str, int]] = defaultdict(lambda: {"adopted": 0, "rejected": 0})
    for row in rows:
        if row.feedback not in {"adopted", "rejected"}:
            continue
        fingerprint = build_error_fingerprint(
            case_type=row.case_type,
            step_name=row.step_name,
            error_message=row.error_message,
            response_status_code=row.response_status_code,
        )
        buckets[(fingerprint, row.case_type)][row.feedback] += 1

    summaries: list[FeedbackSummary] = []
    for (fingerprint, case_type), counts in buckets.items():
        adopted = counts["adopted"]
        rejected = counts["rejected"]
        total = adopted + rejected
        if total <= 0:
            continue
        summaries.append(
            FeedbackSummary(
                error_fingerprint=fingerprint,
                case_type=case_type,
                total_count=total,
                adopted_count=adopted,
                rejected_count=rejected,
                adopted_rate=adopted / total,
            )
        )
    return summaries


async def collect_feedback_rows(db: AsyncSession, *, since: datetime) -> list[FeedbackRow]:
    result = await db.execute(
        select(StepResult, TestCase.case_type)
        .join(TestRun, StepResult.run_id == TestRun.id)
        .join(TestCase, TestRun.case_id == TestCase.id)
        .where(
            StepResult.healing_feedback.in_(["adopted", "rejected"]),
            StepResult.healing_feedback_at.is_not(None),
            StepResult.healing_feedback_at >= since,
        )
    )

    rows: list[FeedbackRow] = []
    for step, case_type_value in result.all():
        response_status = None
        if isinstance(step.response_data, dict):
            response_status = step.response_data.get("status_code")
        case_type = case_type_value.value if hasattr(case_type_value, "value") else str(case_type_value)
        rows.append(
            FeedbackRow(
                case_type=case_type,
                step_name=step.name,
                error_message=step.error_message,
                response_status_code=response_status,
                feedback=step.healing_feedback,
            )
        )
    return rows


async def upsert_feedback_summaries(
    db: AsyncSession,
    summaries: Iterable[FeedbackSummary],
    *,
    aggregated_at: datetime,
) -> int:
    changed = 0
    for summary in summaries:
        result = await db.execute(
            select(HealingFeedbackAggregate).where(
                HealingFeedbackAggregate.error_fingerprint == summary.error_fingerprint,
                HealingFeedbackAggregate.case_type == summary.case_type,
            )
        )
        aggregate = result.scalar_one_or_none()
        if aggregate is None:
            aggregate = HealingFeedbackAggregate(
                error_fingerprint=summary.error_fingerprint,
                case_type=summary.case_type,
            )
            db.add(aggregate)

        aggregate.total_count = summary.total_count
        aggregate.adopted_count = summary.adopted_count
        aggregate.rejected_count = summary.rejected_count
        aggregate.adopted_rate = summary.adopted_rate
        aggregate.last_aggregated_at = aggregated_at
        changed += 1

    if changed:
        await db.commit()
    return changed


async def aggregate_healing_feedback(
    db: AsyncSession,
    *,
    window_days: int = 7,
    now: datetime | None = None,
) -> dict:
    aggregated_at = now or datetime.now(timezone.utc)
    since = aggregated_at - timedelta(days=window_days)
    rows = await collect_feedback_rows(db, since=since)
    summaries = summarize_feedback_rows(rows)
    changed = await upsert_feedback_summaries(db, summaries, aggregated_at=aggregated_at)
    return {
        "window_days": window_days,
        "input_count": len(rows),
        "aggregate_count": len(summaries),
        "upserted": changed,
        "aggregated_at": aggregated_at.isoformat(),
    }
