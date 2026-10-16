"""基于视觉大模型 (VLM) 的 UI 页面语义完整性断言 REST API (T2.1)。"""

from __future__ import annotations

from typing import Any
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field

from app.api.deps import get_current_user, require_engineer
from app.models.user import User
from app.services.vlm_ui_semantic_assertion_reasoner import (
    RULE_TYPES_METADATA,
    VisualAssertionRuleInput,
    VisualAssertionRuleType,
    clear_vlm_assertion_store,
    evaluate_visual_semantic_assertions,
    get_vlm_assertion_report,
    list_vlm_assertion_reports,
)

router = APIRouter(prefix="/visual-ai/semantic-assertion", tags=["VLM 视觉智能断言 (T2.1)"])


class VisualRuleIn(BaseModel):
    rule_type: str = Field(..., description="断言规则类型 (ASSERT_NO_WHITE_SCREEN, ASSERT_KEY_ELEMENT_VISIBLE 等)")
    target_description: str = Field(default="", description="目标元素或状态描述")
    custom_prompt: str | None = Field(default=None, description="自然语言提示词")
    expected_bounding_box: dict[str, int] | None = Field(default=None, description="预期空间坐标范围")


class EvaluateVisualAssertionIn(BaseModel):
    page_name: str = Field(default="order_checkout_page", description="页面名称或路由")
    rules: list[VisualRuleIn] = Field(..., min_length=1, description="视觉断言规则集")
    simulated_white_screen_ratio: float = Field(default=0.0, ge=0.0, le=1.0)
    simulated_broken_images_count: int = Field(default=0, ge=0)
    simulated_missing_element_names: list[str] | None = Field(default=None)
    simulated_is_loading_stuck: bool = Field(default=False)


@router.post("/evaluate")
async def evaluate_assertions_endpoint(
    body: EvaluateVisualAssertionIn,
    _user: User = Depends(get_current_user),
) -> dict[str, Any]:
    """对页面截图执行视觉多模态语义推导与智能断言。"""
    _ = _user
    parsed_rules = [
        VisualAssertionRuleInput(
            rule_type=VisualAssertionRuleType(r.rule_type),
            target_description=r.target_description,
            custom_prompt=r.custom_prompt,
            expected_bounding_box=r.expected_bounding_box,
        )
        for r in body.rules
    ]
    report = evaluate_visual_semantic_assertions(
        page_name=body.page_name,
        rules=parsed_rules,
        simulated_white_screen_ratio=body.simulated_white_screen_ratio,
        simulated_broken_images_count=body.simulated_broken_images_count,
        simulated_missing_element_names=body.simulated_missing_element_names,
        simulated_is_loading_stuck=body.simulated_is_loading_stuck,
    )
    return {"message": "视觉语义多模态断言推导完成", "report": report.to_dict()}


@router.get("/rule-types")
async def list_rule_types_endpoint(
    _user: User = Depends(get_current_user),
) -> dict[str, Any]:
    """获取支持的视觉断言规则类型定义。"""
    _ = _user
    return {"total": len(RULE_TYPES_METADATA), "rules": RULE_TYPES_METADATA}


@router.get("/reports")
async def list_reports_endpoint(
    limit: int = 50,
    _user: User = Depends(get_current_user),
) -> dict[str, Any]:
    """获取历史视觉断言报告列表。"""
    _ = _user
    reports = list_vlm_assertion_reports(limit=limit)
    return {"total": len(reports), "reports": reports}


@router.get("/reports/{report_id}")
async def get_report_endpoint(
    report_id: str,
    _user: User = Depends(get_current_user),
) -> dict[str, Any]:
    """获取单次视觉断言报告详情。"""
    _ = _user
    report = get_vlm_assertion_report(report_id)
    if not report:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"报告 [{report_id}] 不存在")
    return {"report": report.to_dict()}


@router.delete("/reports")
async def clear_reports_endpoint(
    _user: User = Depends(require_engineer),
) -> dict[str, Any]:
    """清空视觉断言报告历史（需工程师权限）。"""
    _ = _user
    clear_vlm_assertion_store()
    return {"message": "已清空所有视觉语义断言报告"}
