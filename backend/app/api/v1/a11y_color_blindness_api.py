"""色盲与低视力多模态视觉感知模拟 REST API (T3.3)。"""

from __future__ import annotations

from typing import Any
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field

from app.api.deps import get_current_user, require_engineer
from app.models.user import User
from app.services.color_blindness_simulation_classifier import (
    audit_color_blindness_accessibility,
    clear_cvd_report_store,
    get_color_blindness_report,
    list_color_blindness_reports,
    simulate_color_vision_deficiency,
)

router = APIRouter(prefix="/a11y/color-blindness", tags=["色盲模拟与低视力分类 (T3.3)"])


class SimulateColorIn(BaseModel):
    hex_color: str = Field(default="#22C55E", description="待转换的 HEX 颜色")


class StatusIndicatorIn(BaseModel):
    element_id: str = Field(..., description="指示器标识")
    color_hex: str = Field(..., description="指示器颜色 HEX")
    has_text: bool = Field(default=False, description="是否伴随文字标签")
    has_icon: bool = Field(default=False, description="是否伴随形状图标 (如勾/叉/感叹号)")
    status_meaning: str = Field(default="normal", description="状态业务语义: success, failure, warning, running")


class AuditColorBlindnessIn(BaseModel):
    component_or_page: str = Field(default="test_run_card", description="被审计组件或页面名称")
    status_indicators: list[StatusIndicatorIn] = Field(..., min_length=1, description="页面关键状态指示列表")


@router.post("/simulate-color")
async def simulate_color_endpoint(
    body: SimulateColorIn,
    _user: User = Depends(get_current_user),
) -> dict[str, Any]:
    """将指定颜色转换为红盲、绿盲、蓝盲、全色盲视角下的仿真色值。"""
    _ = _user
    sim = simulate_color_vision_deficiency(body.hex_color)
    return {"message": "色盲视觉仿真计算完成", "simulation": sim.to_dict()}


@router.post("/audit")
async def audit_color_blindness_endpoint(
    body: AuditColorBlindnessIn,
    _user: User = Depends(get_current_user),
) -> dict[str, Any]:
    """审查页面状态指示是否符合 WCAG 1.4.1 (禁止仅依赖颜色传达关键信息)。"""
    _ = _user
    indicators_dicts = [i.model_dump() for e in [body.status_indicators] for i in e]
    report = audit_color_blindness_accessibility(
        component_or_page=body.component_or_page,
        status_indicators=indicators_dicts,
    )
    return {"message": "WCAG 1.4.1 色盲多模态审计完成", "report": report.to_dict()}


@router.get("/reports")
async def list_reports_endpoint(
    limit: int = 50,
    _user: User = Depends(get_current_user),
) -> dict[str, Any]:
    """获取历史色盲审计报告列表。"""
    _ = _user
    reports = list_color_blindness_reports(limit=limit)
    return {"total": len(reports), "reports": reports}


@router.get("/reports/{report_id}")
async def get_report_endpoint(
    report_id: str,
    _user: User = Depends(get_current_user),
) -> dict[str, Any]:
    """按 ID 查询单次色盲审计报告详情。"""
    _ = _user
    report = get_color_blindness_report(report_id)
    if not report:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"报告 [{report_id}] 不存在")
    return {"report": report.to_dict()}


@router.delete("/reports")
async def clear_reports_endpoint(
    _user: User = Depends(require_engineer),
) -> dict[str, Any]:
    """清空色盲审计报告仓库 (需工程师权限)。"""
    _ = _user
    clear_cvd_report_store()
    return {"message": "已清空所有色盲多模态审计报告"}
