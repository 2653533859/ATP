"""键盘导航流转与焦点可达性 REST API (T3.2)。"""

from __future__ import annotations

from typing import Any
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field

from app.api.deps import get_current_user, require_engineer
from app.models.user import User
from app.services.a11y_keyboard_navigation_path_verifier import (
    clear_keyboard_nav_store,
    get_keyboard_nav_report,
    list_keyboard_nav_reports,
    simulate_keyboard_navigation,
)

router = APIRouter(prefix="/a11y/keyboard-nav", tags=["键盘全盲导航与焦点流转 (T3.2)"])


class KeyboardElementIn(BaseModel):
    element_id: str | None = Field(default=None, description="DOM 节点唯一标识")
    tag_name: str = Field(default="button", description="HTML 标签名 (如 button, a, input)")
    tabindex: int | None = Field(default=None, description="tabindex 属性值")
    text_content: str | None = Field(default=None, description="文本或子标签文本")
    has_focus_ring: bool = Field(default=True, description="是否具有可见聚焦环样式")
    container_id: str | None = Field(default=None, description="父级容器或弹窗 ID")
    is_focus_trapped: bool = Field(default=False, description="是否处于无解死锁循环中")


class SimulateKeyboardNavIn(BaseModel):
    page_name: str = Field(default="checkout_modal", description="页面或弹窗场景名")
    elements: list[KeyboardElementIn] = Field(..., min_length=1, description="可聚焦节点与交互项列表")


@router.post("/simulate")
async def simulate_keyboard_nav_endpoint(
    body: SimulateKeyboardNavIn,
    _user: User = Depends(get_current_user),
) -> dict[str, Any]:
    """仿真 Tab 序列化键盘流转，检查焦点陷阱死锁、指示器剥离与顺序错乱。"""
    _ = _user
    elements_dicts = [e.model_dump() for e in body.elements]
    report = simulate_keyboard_navigation(
        page_name=body.page_name,
        elements=elements_dicts,
    )
    return {"message": "键盘导航流转仿真审计完成", "report": report.to_dict()}


@router.get("/reports")
async def list_reports_endpoint(
    limit: int = 50,
    _user: User = Depends(get_current_user),
) -> dict[str, Any]:
    """获取历史键盘导航审计报告列表。"""
    _ = _user
    reports = list_keyboard_nav_reports(limit=limit)
    return {"total": len(reports), "reports": reports}


@router.get("/reports/{report_id}")
async def get_report_endpoint(
    report_id: str,
    _user: User = Depends(get_current_user),
) -> dict[str, Any]:
    """按 ID 查询单次键盘导航报告详情。"""
    _ = _user
    report = get_keyboard_nav_report(report_id)
    if not report:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"报告 [{report_id}] 不存在")
    return {"report": report.to_dict()}


@router.delete("/reports")
async def clear_reports_endpoint(
    _user: User = Depends(require_engineer),
) -> dict[str, Any]:
    """清空键盘导航审计报告仓库 (需工程师权限)。"""
    _ = _user
    clear_keyboard_nav_store()
    return {"message": "已清空所有键盘导航审计报告"}
