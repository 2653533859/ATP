from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import require_admin
from app.core.database import get_db
from app.models.healing_prompt_example import HealingPromptExample
from app.models.user import User
from app.schemas.healing_prompt_example import (
    HealingPromptExampleOut,
    HealingPromptExampleUpdateIn,
)
from app.services.healing_prompt_examples import (
    create_example_from_step,
    list_prompt_examples,
)

router = APIRouter(prefix="/ai-healing/examples", tags=["AI 自愈示例"])


@router.get("", response_model=list[HealingPromptExampleOut])
async def list_examples(
    error_fingerprint: str | None = None,
    case_type: str | None = None,
    high_quality: bool | None = None,
    limit: int = Query(100, ge=1, le=500),
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_admin),
):
    return await list_prompt_examples(
        db,
        error_fingerprint=error_fingerprint,
        case_type=case_type,
        high_quality=high_quality,
        limit=limit,
    )


@router.post("/from-step/{step_result_id}", response_model=HealingPromptExampleOut, status_code=status.HTTP_201_CREATED)
async def create_from_step(
    step_result_id: int,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_admin),
):
    try:
        return await create_example_from_step(db, step_result_id=step_result_id, marked_by=user.id)
    except ValueError as exc:
        detail_map = {
            "step_not_found": (404, "步骤结果不存在"),
            "step_feedback_not_adopted": (400, "仅能从已采纳的自愈反馈创建示例"),
            "step_suggestion_empty": (400, "自愈建议为空，无法创建示例"),
            "run_not_found": (404, "执行记录不存在"),
            "case_not_found": (404, "用例不存在"),
        }
        code, detail = detail_map.get(str(exc), (400, "创建示例失败"))
        raise HTTPException(status_code=code, detail=detail)


@router.patch("/{example_id}", response_model=HealingPromptExampleOut)
async def update_example(
    example_id: int,
    body: HealingPromptExampleUpdateIn,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_admin),
):
    example = await db.get(HealingPromptExample, example_id)
    if example is None:
        raise HTTPException(status_code=404, detail="示例不存在")

    payload = body.model_dump(exclude_none=True)
    if "suggestion_text" in payload:
        example.suggestion_text = payload["suggestion_text"]
    if "marked_high_quality" in payload:
        example.marked_high_quality = payload["marked_high_quality"]
        example.marked_by = user.id
        example.marked_at = datetime.now(timezone.utc)

    await db.commit()
    await db.refresh(example)
    return example


@router.delete("/{example_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_example(
    example_id: int,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_admin),
):
    example = await db.get(HealingPromptExample, example_id)
    if example is None:
        raise HTTPException(status_code=404, detail="示例不存在")
    await db.delete(example)
    await db.commit()
