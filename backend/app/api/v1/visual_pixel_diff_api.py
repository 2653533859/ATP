"""多视口像素级 SSIM 结构相似度比对 REST API (T1.1)。"""

from __future__ import annotations

from typing import Any
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field

from app.api.deps import get_current_user, require_engineer
from app.models.user import User
from app.services.visual_pixel_ssim_diff_engine import (
    clear_visual_diff_store,
    compare_multi_viewports_visual_diff,
    get_visual_diff_report,
    list_visual_diff_reports,
)

router = APIRouter(prefix="/visual/pixel-diff", tags=["像素级视觉比对 (T1.1)"])


class CompareViewportsIn(BaseModel):
    snapshot_name: str = Field(default="home_page_checkout", description="快照标识名称")
    viewports: list[str] | None = Field(default=None, description="需要比对的视口列表 (DESKTOP, TABLET, MOBILE)")
    tolerance_threshold: float = Field(default=0.98, ge=0.5, le=1.0, description="SSIM 结构相似度容差阈值 (0.5~1.0)")
    simulated_viewport_diffs: dict[str, int] | None = Field(default=None, description="各视口模拟差异像素数字典")


@router.post("/compare")
async def compare_visual_diff_endpoint(
    body: CompareViewportsIn,
    _user: User = Depends(get_current_user),
) -> dict[str, Any]:
    """并发执行多视口跨分辨率像素级视觉差异与 SSIM 比对。"""
    _ = _user
    report = compare_multi_viewports_visual_diff(
        snapshot_name=body.snapshot_name,
        viewports=body.viewports,
        tolerance_threshold=body.tolerance_threshold,
        simulated_viewport_diffs=body.simulated_viewport_diffs,
    )
    return {"message": "多视口像素级视觉比对完成", "report": report.to_dict()}


@router.get("/reports")
async def list_reports_endpoint(
    limit: int = 50,
    _user: User = Depends(get_current_user),
) -> dict[str, Any]:
    """获取历史视觉比对报告列表。"""
    _ = _user
    reports = list_visual_diff_reports(limit=limit)
    return {"total": len(reports), "reports": reports}


@router.get("/reports/{report_id}")
async def get_report_endpoint(
    report_id: str,
    _user: User = Depends(get_current_user),
) -> dict[str, Any]:
    """查询单次视觉比对报告详情。"""
    _ = _user
    report = get_visual_diff_report(report_id)
    if not report:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"报告 [{report_id}] 不存在")
    return {"report": report.to_dict()}


@router.delete("/reports")
async def clear_reports_endpoint(
    _user: User = Depends(require_engineer),
) -> dict[str, Any]:
    """清空所有视觉比对报告（需工程师权限）。"""
    _ = _user
    clear_visual_diff_store()
    return {"message": "已清空所有视觉比对报告"}
