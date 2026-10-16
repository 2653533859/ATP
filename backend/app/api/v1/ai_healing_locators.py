"""AI 驱动的选择器智能自愈与多模态恢复 API (D2.1)."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field

from app.api.deps import get_current_user
from app.models.user import User
from app.services.smart_locator_healing_engine import (
    BrokenLocatorContext,
    ElementFingerprint,
    LocatorType,
    heal_broken_locator,
    list_healing_history,
    parse_dom_elements_snapshot,
)

router = APIRouter(prefix="/ai-healing/locators", tags=["AI 失效选择器智能自愈"])


class HealLocatorIn(BaseModel):
    original_locator: str = Field(min_length=1, max_length=256, description="原始失效的选择器表达式")
    locator_type: str = Field(default="xpath", description="选择器类型 (xpath | css_selector | id | test_id | text)")
    last_known_fingerprint: dict[str, Any] | None = Field(default=None, description="历史已知的元素指纹快照")
    live_dom_elements: list[dict[str, Any]] = Field(
        default_factory=list, description="当前活动页面抓取到的 DOM / UI 元素快照"
    )
    min_confidence: float = Field(default=0.50, ge=0.1, le=1.0, description="最低采纳置信度阈值")
    error_message: str = Field(default="NoSuchElementException", description="执行框架抛出的原始未找到异常")


@router.post("/heal")
async def heal_broken_locator_endpoint(
    body: HealLocatorIn,
    _user: User = Depends(get_current_user),
) -> dict[str, Any]:
    """对因前端重构导致失效的选择器执行多模态加权差分自愈推导。"""
    _ = _user
    try:
        loc_type = LocatorType(body.locator_type.lower())
    except ValueError:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"不支持的选择器类型: {body.locator_type}")

    fingerprint = None
    if body.last_known_fingerprint:
        fingerprint = ElementFingerprint(
            tag_name=str(body.last_known_fingerprint.get("tag_name", "button")),
            text_content=body.last_known_fingerprint.get("text_content"),
            element_id=body.last_known_fingerprint.get("element_id"),
            class_names=body.last_known_fingerprint.get("class_names") or [],
            attributes=body.last_known_fingerprint.get("attributes") or {},
            parent_tag=body.last_known_fingerprint.get("parent_tag"),
            xpath=body.last_known_fingerprint.get("xpath"),
            bounding_box=body.last_known_fingerprint.get("bounding_box"),
        )

    context = BrokenLocatorContext(
        original_locator=body.original_locator,
        locator_type=loc_type,
        last_known_fingerprint=fingerprint,
        error_message=body.error_message,
    )

    live_elements = parse_dom_elements_snapshot(body.live_dom_elements)
    result = heal_broken_locator(context, live_elements, min_confidence=body.min_confidence)
    return result.to_dict()


@router.get("/history")
async def list_healing_history_endpoint(
    _user: User = Depends(get_current_user),
) -> dict[str, Any]:
    """查询选择器自愈评估审计记录流水。"""
    _ = _user
    history = list_healing_history()
    return {"total": len(history), "history": [r.to_dict() for r in history]}
