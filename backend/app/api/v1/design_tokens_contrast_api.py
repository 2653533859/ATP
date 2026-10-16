"""设计规范 Token 与色彩对比度检查 REST API (T2.3)。"""

from __future__ import annotations

from typing import Any
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field

from app.api.deps import get_current_user, require_engineer
from app.models.user import User
from app.services.design_system_token_contrast_checker import (
    audit_design_tokens_and_contrast,
    calculate_contrast_ratio,
    clear_design_audit_store,
    get_design_system_report,
    list_design_system_reports,
)

router = APIRouter(prefix="/visual-ai/design-tokens", tags=["设计系统与对比度检查 (T2.3)"])


class ElementStyleIn(BaseModel):
    element_id: str = Field(...)
    color: str | None = Field(default=None, description="前景色 HEX (如 #0F172A)")
    background_color: str | None = Field(default=None, description="背景色 HEX (如 #FFFFFF)")
    font_size: float | None = Field(default=None, description="字号大小 px")
    is_bold: bool = Field(default=False)
    padding: float | None = Field(default=None, description="内边距 px")
    border_radius: float | None = Field(default=None, description="圆角 px")


class AuditDesignTokensIn(BaseModel):
    target_name: str = Field(default="order_page_styles", description="审计目标")
    elements: list[ElementStyleIn] = Field(..., min_length=1)


class ComputeContrastIn(BaseModel):
    foreground_hex: str = Field(..., description="前景色 HEX")
    background_hex: str = Field(..., description="背景色 HEX")


@router.post("/audit")
async def audit_design_tokens_endpoint(
    body: AuditDesignTokensIn,
    _user: User = Depends(get_current_user),
) -> dict[str, Any]:
    """对页面元素样式执行 Design System Token 规范与 WCAG 对比度合规审计。"""
    _ = _user
    elements_dicts = [e.model_dump() for e in body.elements]
    report = audit_design_tokens_and_contrast(
        target_name=body.target_name,
        elements=elements_dicts,
    )
    return {"message": "设计系统与色彩对比度审计完成", "report": report.to_dict()}


@router.post("/compute-contrast")
async def compute_contrast_endpoint(
    body: ComputeContrastIn,
    _user: User = Depends(get_current_user),
) -> dict[str, Any]:
    """快速计算两组颜色的 WCAG 相对色彩对比度与合规评级。"""
    _ = _user
    ratio = calculate_contrast_ratio(body.foreground_hex, body.background_hex)
    is_aa_pass = ratio >= 4.5
    is_aaa_pass = ratio >= 7.0
    return {
        "foreground_hex": body.foreground_hex,
        "background_hex": body.background_hex,
        "contrast_ratio": round(ratio, 2),
        "is_wcag_aa_pass": is_aa_pass,
        "is_wcag_aaa_pass": is_aaa_pass,
        "rating": "AAA" if is_aaa_pass else ("AA" if is_aa_pass else "FAIL"),
    }


@router.get("/reports")
async def list_reports_endpoint(
    limit: int = 50,
    _user: User = Depends(get_current_user),
) -> dict[str, Any]:
    """获取历史设计系统审计报告列表。"""
    _ = _user
    reports = list_design_system_reports(limit=limit)
    return {"total": len(reports), "reports": reports}


@router.get("/reports/{report_id}")
async def get_report_endpoint(
    report_id: str,
    _user: User = Depends(get_current_user),
) -> dict[str, Any]:
    """查询单次设计系统审计报告详情。"""
    _ = _user
    report = get_design_system_report(report_id)
    if not report:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"报告 [{report_id}] 不存在")
    return {"report": report.to_dict()}


@router.delete("/reports")
async def clear_reports_endpoint(
    _user: User = Depends(require_engineer),
) -> dict[str, Any]:
    """清空设计系统审计报告（需工程师权限）。"""
    _ = _user
    clear_design_audit_store()
    return {"message": "已清空所有设计系统与对比度审计报告"}
