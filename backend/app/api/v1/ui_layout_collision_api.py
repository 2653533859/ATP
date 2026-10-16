"""跨视口布局溢出与元素碰撞检测 REST API (T2.2)。"""

from __future__ import annotations

from typing import Any
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field

from app.api.deps import get_current_user, require_engineer
from app.models.user import User
from app.services.ui_layout_overflow_collision_detector import (
    clear_layout_defect_store,
    detect_layout_defects,
    get_layout_defect_report,
    list_layout_defect_reports,
)

router = APIRouter(prefix="/visual-ai/layout-collision", tags=["布局碰撞与溢出检测 (T2.2)"])


class ElementBoxIn(BaseModel):
    element_id: str = Field(...)
    tag_name: str = Field(default="div")
    x: float = Field(..., ge=0)
    y: float = Field(..., ge=0)
    width: float = Field(..., ge=0)
    height: float = Field(..., ge=0)
    scroll_width: float | None = Field(default=None)
    scroll_height: float | None = Field(default=None)
    text_content: str = Field(default="")
    z_index: int = Field(default=0)
    parent_id: str | None = Field(default=None)


class DetectLayoutIn(BaseModel):
    page_name: str = Field(default="checkout_mobile_screen")
    viewport_width: int = Field(default=375, ge=100, le=4000)
    viewport_height: int = Field(default=812, ge=100, le=4000)
    elements: list[ElementBoxIn] = Field(..., min_length=1)


@router.post("/detect")
async def detect_layout_endpoint(
    body: DetectLayoutIn,
    _user: User = Depends(get_current_user),
) -> dict[str, Any]:
    """对页面元素几何边界盒执行视口水平溢出与 AABB 碰撞重叠检测。"""
    _ = _user
    elements_dicts = [e.model_dump() for e in body.elements]
    report = detect_layout_defects(
        page_name=body.page_name,
        viewport_width=body.viewport_width,
        viewport_height=body.viewport_height,
        elements=elements_dicts,
    )
    return {"message": "布局与碰撞检测完成", "report": report.to_dict()}


@router.get("/reports")
async def list_reports_endpoint(
    limit: int = 50,
    _user: User = Depends(get_current_user),
) -> dict[str, Any]:
    """获取历史布局检测报告列表。"""
    _ = _user
    reports = list_layout_defect_reports(limit=limit)
    return {"total": len(reports), "reports": reports}


@router.get("/reports/{report_id}")
async def get_report_endpoint(
    report_id: str,
    _user: User = Depends(get_current_user),
) -> dict[str, Any]:
    """查询单次布局检测报告详情。"""
    _ = _user
    report = get_layout_defect_report(report_id)
    if not report:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"报告 [{report_id}] 不存在")
    return {"report": report.to_dict()}


@router.delete("/reports")
async def clear_reports_endpoint(
    _user: User = Depends(require_engineer),
) -> dict[str, Any]:
    """清空布局检测报告（需工程师权限）。"""
    _ = _user
    clear_layout_defect_store()
    return {"message": "已清空所有布局检测报告"}
