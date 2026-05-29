from __future__ import annotations

import math
from datetime import datetime, timezone
from typing import Sequence

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.case import StepResult, TestCase, TestRun
from app.models.healing_feedback import HealingFeedbackAggregate
from app.models.healing_prompt_example import HealingPromptExample
from app.services.healing_feedback import build_error_fingerprint


def build_step_context(step: StepResult) -> dict:
    return {
        "step_id": step.id,
        "step_index": step.step_index,
        "step_name": step.name,
        "status": step.status.value if hasattr(step.status, "value") else str(step.status),
        "error_message": step.error_message,
        "request_data": step.request_data,
        "response_data": step.response_data,
        "screenshot_url": step.screenshot_url,
    }


def build_few_shot_block(examples: Sequence[HealingPromptExample]) -> str:
    if not examples:
        return ""
    parts = ["# 历史高质量修复示例（仅供参考）"]
    for idx, example in enumerate(examples, start=1):
        context = example.step_context_json or {}
        parts.append(
            "\n".join(
                [
                    f"## 示例 {idx}",
                    f"- 用例类型: {example.case_type}",
                    f"- 失败步骤: {context.get('step_name') or ''}",
                    f"- 错误摘要: {context.get('error_message') or ''}",
                    f"- 采纳建议: {example.suggestion_text}",
                ]
            )
        )
    return "\n\n".join(parts)


def prompt_example_quality_weight(aggregate: HealingFeedbackAggregate | None) -> float:
    if aggregate is None or aggregate.total_count <= 0:
        return 1.0
    confidence = min(math.log1p(aggregate.total_count) / math.log1p(20), 1.0)
    adopted_rate = max(0.0, min(float(aggregate.adopted_rate or 0.0), 1.0))
    return round(1.0 + adopted_rate * 2.0 + confidence, 4)


def _example_timestamp(example: HealingPromptExample) -> float:
    value = example.marked_at or example.created_at
    return value.timestamp() if value else 0.0


async def list_prompt_examples(
    db: AsyncSession,
    *,
    error_fingerprint: str | None = None,
    case_type: str | None = None,
    high_quality: bool | None = None,
    limit: int = 100,
) -> list[HealingPromptExample]:
    stmt = select(HealingPromptExample)
    if error_fingerprint:
        stmt = stmt.where(HealingPromptExample.error_fingerprint == error_fingerprint)
    if case_type:
        stmt = stmt.where(HealingPromptExample.case_type == case_type)
    if high_quality is not None:
        stmt = stmt.where(HealingPromptExample.marked_high_quality == high_quality)
    stmt = stmt.order_by(HealingPromptExample.created_at.desc()).limit(limit)
    result = await db.execute(stmt)
    return list(result.scalars().all())


async def get_high_quality_examples(
    db: AsyncSession,
    *,
    error_fingerprint: str,
    case_type: str,
    limit: int,
) -> list[HealingPromptExample]:
    if limit <= 0:
        return []
    result = await db.execute(
        select(HealingPromptExample, HealingFeedbackAggregate)
        .outerjoin(
            HealingFeedbackAggregate,
            (HealingFeedbackAggregate.error_fingerprint == HealingPromptExample.error_fingerprint)
            & (HealingFeedbackAggregate.case_type == HealingPromptExample.case_type),
        )
        .where(
            HealingPromptExample.error_fingerprint == error_fingerprint,
            HealingPromptExample.case_type == case_type,
            HealingPromptExample.marked_high_quality.is_(True),
        )
        .order_by(HealingPromptExample.created_at.desc())
        .limit(max(limit * 5, limit))
    )
    ranked = sorted(
        result.all(),
        key=lambda row: (
            prompt_example_quality_weight(row[1]),
            _example_timestamp(row[0]),
        ),
        reverse=True,
    )
    return [example for example, _aggregate in ranked[:limit]]


async def create_example_from_step(
    db: AsyncSession,
    *,
    step_result_id: int,
    marked_by: int | None = None,
) -> HealingPromptExample:
    step = await db.get(StepResult, step_result_id)
    if step is None:
        raise ValueError("step_not_found")
    if step.healing_feedback != "adopted":
        raise ValueError("step_feedback_not_adopted")
    if not step.healing_suggestion:
        raise ValueError("step_suggestion_empty")

    run = await db.get(TestRun, step.run_id)
    if run is None:
        raise ValueError("run_not_found")
    case = await db.get(TestCase, run.case_id)
    if case is None:
        raise ValueError("case_not_found")

    case_type = case.case_type.value if hasattr(case.case_type, "value") else str(case.case_type)
    response_status = None
    if isinstance(step.response_data, dict):
        response_status = step.response_data.get("status_code")
    example = HealingPromptExample(
        error_fingerprint=build_error_fingerprint(
            case_type=case_type,
            step_name=step.name,
            error_message=step.error_message,
            response_status_code=response_status,
        ),
        case_type=case_type,
        step_context_json=build_step_context(step),
        suggestion_text=step.healing_suggestion,
        source_step_result_id=step.id,
        marked_high_quality=True,
        marked_by=marked_by,
        marked_at=datetime.now(timezone.utc),
    )
    db.add(example)
    await db.commit()
    await db.refresh(example)
    return example
