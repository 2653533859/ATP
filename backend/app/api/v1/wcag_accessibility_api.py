"""WCAG 2.2 无障碍可访问性 DOM 深度扫描 REST API (T3.1)。"""

from __future__ import annotations

from typing import Any
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field

from app.api.deps import get_current_user, require_engineer
from app.models.user import User
from app.services.wcag_accessibility_deep_scanner import (
    clear_wcag_report_store,
    get_wcag_report,
    list_wcag_reports,
    scan_dom_accessibility,
)

router = APIRouter(prefix="/a11y/wcag-scanner", tags=["无障碍 DOM 深度扫描 (T3.1)"])


class ElementNodeIn(BaseModel):
    element_id: str | None = Field(default=None, description="DOM 节点标识")
    tag_name: str = Field(default="div", description="HTML 标签名 (如 img, button, input)")
    attributes: dict[str, Any] = Field(default_factory=dict, description="节点属性 (如 alt, aria-label, id)")
    text_content: str | None = Field(default=None, description="直接文本内容")
    width: float | None = Field(default=None, description="渲染宽度 px")
    height: float | None = Field(default=None, description="渲染高度 px")
    selector: str | None = Field(default=None, description="CSS 选择器")
    has_associated_label: bool = Field(default=False, description="表单项是否关联有外部 label")
    label_text: str | None = Field(default=None, description="绑定的标签文本")


class ScanDomAccessibilityIn(BaseModel):
    page_url_or_name: str = Field(default="https://atp.example.com/workbench", description="页面 URL 或名称")
    elements: list[ElementNodeIn] = Field(..., min_length=1, description="待扫描 DOM 元素集合")


@router.post("/scan")
async def scan_dom_accessibility_endpoint(
    body: ScanDomAccessibilityIn,
    _user: User = Depends(get_current_user),
) -> dict[str, Any]:
    """对传入的 DOM 树执行全面 WCAG 2.2 无障碍合规性深度扫描。"""
    _ = _user
    elements_dicts = [e.model_dump() for e in body.elements]
    report = scan_dom_accessibility(
        page_url_or_name=body.page_url_or_name,
        elements=elements_dicts,
    )
    return {"message": "WCAG 2.2 无障碍扫描完成", "report": report.to_dict()}


@router.get("/reports")
async def list_reports_endpoint(
    limit: int = 50,
    _user: User = Depends(get_current_user),
) -> dict[str, Any]:
    """获取历史 WCAG 无障碍扫描报告列表。"""
    _ = _user
    reports = list_wcag_reports(limit=limit)
    return {"total": len(reports), "reports": reports}


@router.get("/reports/{report_id}")
async def get_report_endpoint(
    report_id: str,
    _user: User = Depends(get_current_user),
) -> dict[str, Any]:
    """按 ID 查询单次 WCAG 无障碍扫描报告详情。"""
    _ = _user
    report = get_wcag_report(report_id)
    if not report:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"报告 [{report_id}] 不存在")
    return {"report": report.to_dict()}


@router.delete("/reports")
async def clear_reports_endpoint(
    _user: User = Depends(require_engineer),
) -> dict[str, Any]:
    """清空 WCAG 无障碍扫描报告仓库 (需工程师权限)。"""
    _ = _user
    clear_wcag_report_store()
    return {"message": "已清空所有 WCAG 扫描报告"}
