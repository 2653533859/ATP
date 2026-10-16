"""动态忽略掩码与抗锯齿微噪声过滤 REST API (T1.2)。"""

from __future__ import annotations

from typing import Any
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field

from app.api.deps import get_current_user, require_engineer
from app.models.user import User
from app.services.visual_anti_aliasing_noise_filter import (
    clear_noise_filter_store,
    filter_visual_noise_and_mask,
    get_noise_filter_report,
    list_mask_regions,
    list_noise_filter_reports,
    register_mask_region,
)

router = APIRouter(prefix="/visual/noise-filter", tags=["视觉智能去噪与掩码 (T1.2)"])


class MaskRegionIn(BaseModel):
    name: str = Field(..., description="掩码名称 (如 timestamp_banner)")
    x: int = Field(..., ge=0)
    y: int = Field(..., ge=0)
    width: int = Field(..., ge=1)
    height: int = Field(..., ge=1)
    reason: str = Field(default="动态组件忽略")


class ApplyFilterIn(BaseModel):
    target_name: str = Field(default="checkout_screen", description="对比目标名称")
    raw_pixels: list[dict[str, Any]] = Field(..., description="差异像素点列表")
    active_mask_ids: list[str] | None = Field(default=None)
    extra_masks: list[MaskRegionIn] | None = Field(default=None)
    canvas_width: int = Field(default=1920)
    canvas_height: int = Field(default=1080)
    anti_aliasing_threshold_delta_e: float = Field(default=20.0, ge=1.0, le=100.0)


@router.post("/apply")
async def apply_filter_endpoint(
    body: ApplyFilterIn,
    _user: User = Depends(get_current_user),
) -> dict[str, Any]:
    """对像素差异集执行掩码遮盖与抗锯齿微噪点过滤，输出纯净差异报告。"""
    _ = _user
    extra_dicts = [m.model_dump() for m in body.extra_masks] if body.extra_masks is not None else None
    report = filter_visual_noise_and_mask(
        target_name=body.target_name,
        raw_pixels=body.raw_pixels,
        active_mask_ids=body.active_mask_ids,
        extra_masks=extra_dicts,
        canvas_width=body.canvas_width,
        canvas_height=body.canvas_height,
        anti_aliasing_threshold_delta_e=body.anti_aliasing_threshold_delta_e,
    )
    return {"message": "视觉掩码与抗锯齿去噪处理完成", "report": report.to_dict()}


@router.post("/masks")
async def register_mask_endpoint(
    body: MaskRegionIn,
    _user: User = Depends(require_engineer),
) -> dict[str, Any]:
    """登记常用动态忽略掩码区域（需工程师权限）。"""
    _ = _user
    region = register_mask_region(
        name=body.name,
        x=body.x,
        y=body.y,
        width=body.width,
        height=body.height,
        reason=body.reason,
    )
    return {"message": "动态忽略掩码区域登记成功", "mask": region.to_dict()}


@router.get("/masks")
async def list_masks_endpoint(
    _user: User = Depends(get_current_user),
) -> dict[str, Any]:
    """查询已登记的忽略掩码库列表。"""
    _ = _user
    masks = list_mask_regions()
    return {"total": len(masks), "masks": masks}


@router.get("/reports")
async def list_reports_endpoint(
    limit: int = 50,
    _user: User = Depends(get_current_user),
) -> dict[str, Any]:
    """获取历史去噪审计报告列表。"""
    _ = _user
    reports = list_noise_filter_reports(limit=limit)
    return {"total": len(reports), "reports": reports}


@router.get("/reports/{report_id}")
async def get_report_endpoint(
    report_id: str,
    _user: User = Depends(get_current_user),
) -> dict[str, Any]:
    """查询单次去噪审计报告详情。"""
    _ = _user
    report = get_noise_filter_report(report_id)
    if not report:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"报告 [{report_id}] 不存在")
    return {"report": report.to_dict()}


@router.delete("/reports")
async def clear_reports_endpoint(
    _user: User = Depends(require_engineer),
) -> dict[str, Any]:
    """清空掩码库与去噪报告（需工程师权限）。"""
    _ = _user
    clear_noise_filter_store()
    return {"message": "已清空所有视觉掩码与去噪报告"}
