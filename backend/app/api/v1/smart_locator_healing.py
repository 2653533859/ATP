"""UI 元素定位多策略自愈与降级重试 REST API (T4.1)。"""

from __future__ import annotations

from typing import Any
from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field

from app.api.deps import get_current_user, require_engineer
from app.models.user import User
from app.services.smart_locator_multistrategy_healer import (
    CandidateElement,
    TargetElementSpec,
    clear_healing_history,
    get_healing_history,
    get_healing_statistics,
    heal_broken_locator,
)

router = APIRouter(prefix="/healing/locator", tags=["UI元素多策略自愈重试 (T4.1)"])


class TargetSpecIn(BaseModel):
    original_locator: str = Field(..., description="失效的历史选择器 (如 //button[@id='submit-btn'])")
    tag_name: str = Field(default="button", description="期望元素标签名")
    text_content: str = Field(default="", description="期望元素可见文本内容")
    test_id: str = Field(default="", description="期望元素 data-testid")
    attributes: dict[str, str] = Field(default_factory=dict, description="辅助属性指纹")
    bounding_box: dict[str, float] = Field(default_factory=dict, description="几何外接矩形 (x, y, width, height)")


class CandidateElementIn(BaseModel):
    candidate_id: str = Field(..., description="候选节点临时 ID")
    tag_name: str = Field(..., description="候选节点标签名")
    text_content: str = Field(default="", description="候选节点文本")
    test_id: str = Field(default="", description="候选节点 test-id")
    attributes: dict[str, str] = Field(default_factory=dict, description="属性列表")
    bounding_box: dict[str, float] = Field(default_factory=dict, description="几何外接矩形")
    xpath: str = Field(default="", description="候选节点的当前物理 xpath")


class HealLocatorIn(BaseModel):
    target: TargetSpecIn = Field(..., description="目标失效元素特征描述")
    candidates: list[CandidateElementIn] = Field(..., min_length=1, description="当前页面采集到的候选 DOM 节点列表")
    execute_retry: bool = Field(default=True, description="是否模拟降级重试执行")


@router.post("/heal")
async def heal_locator_endpoint(
    body: HealLocatorIn,
    _user: User = Depends(get_current_user),
) -> dict[str, Any]:
    """结合文本/ID/XPath/语义距离多策略加权推导自愈定位器并执行降级重试。"""
    _ = _user
    target_spec = TargetElementSpec(
        original_locator=body.target.original_locator,
        tag_name=body.target.tag_name,
        text_content=body.target.text_content,
        test_id=body.target.test_id,
        attributes=body.target.attributes,
        bounding_box=body.target.bounding_box,
    )
    cands = [
        CandidateElement(
            candidate_id=c.candidate_id,
            tag_name=c.tag_name,
            text_content=c.text_content,
            test_id=c.test_id,
            attributes=c.attributes,
            bounding_box=c.bounding_box,
            xpath=c.xpath,
        )
        for c in body.candidates
    ]

    result = heal_broken_locator(
        target=target_spec,
        candidates=cands,
        execute_retry=body.execute_retry,
    )
    return {"message": "选择器自愈计算完成", "result": result.to_dict()}


@router.get("/history")
async def get_history_endpoint(
    limit: int = 50,
    _user: User = Depends(get_current_user),
) -> dict[str, Any]:
    """查询自愈事件审计历史与成功率统计。"""
    _ = _user
    history = get_healing_history(limit=limit)
    stats = get_healing_statistics()
    return {
        "statistics": stats,
        "history": [h.to_dict() for h in history],
    }


@router.delete("/history")
async def clear_history_endpoint(
    _user: User = Depends(require_engineer),
) -> dict[str, Any]:
    """清空自愈审计历史 (需工程师权限)。"""
    _ = _user
    c = clear_healing_history()
    return {"message": f"已清空 {c} 条自愈记录", "cleared_count": c}
