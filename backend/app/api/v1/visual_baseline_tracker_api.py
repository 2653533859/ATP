"""多版本视觉黄金基线管理与跨分支追踪 REST API (T1.3)。"""

from __future__ import annotations

from typing import Any
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field

from app.api.deps import get_current_user, require_engineer
from app.models.user import User
from app.services.visual_golden_baseline_branch_tracker import (
    clear_baseline_tracker_store,
    compare_cross_branch_baselines,
    get_visual_baseline,
    list_visual_baselines,
    promote_baseline_to_golden,
    register_visual_baseline,
)

router = APIRouter(prefix="/visual/baselines", tags=["视觉黄金基线管理 (T1.3)"])


class RegisterBaselineIn(BaseModel):
    page_route: str = Field(..., description="页面路径 (如 /checkout 或 /dashboard)")
    branch_name: str = Field(default="main", description="所属代码分支")
    version_tag: str = Field(default="v1.0.0", description="版本号标签")
    viewport_snapshots: dict[str, str] = Field(..., description="各视口快照哈希映射")
    changelog: str = Field(default="提交视觉基线更新")
    is_active_golden: bool = Field(default=False)


class CompareCrossBranchIn(BaseModel):
    page_route: str = Field(..., description="比对页面路径")
    source_branch: str = Field(..., description="来源分支 (如 feat/checkout-redesign)")
    target_branch: str = Field(default="main", description="目标主干分支")


@router.post("/register")
async def register_baseline_endpoint(
    body: RegisterBaselineIn,
    user: User = Depends(get_current_user),
) -> dict[str, Any]:
    """登记新的页面多视口视觉基线快照。"""
    snapshot = register_visual_baseline(
        page_route=body.page_route,
        branch_name=body.branch_name,
        version_tag=body.version_tag,
        viewport_snapshots=body.viewport_snapshots,
        approved_by=user.username or "tester",
        is_active_golden=body.is_active_golden,
        changelog=body.changelog,
    )
    return {"message": "视觉基线快照登记成功", "baseline": snapshot.to_dict()}


@router.post("/{baseline_id}/promote")
async def promote_baseline_endpoint(
    baseline_id: str,
    user: User = Depends(require_engineer),
) -> dict[str, Any]:
    """将候选基线审批提升为当前分支的生效黄金基线（需工程师权限）。"""
    res = promote_baseline_to_golden(
        baseline_id=baseline_id,
        approver=user.username or "lead_engineer",
    )
    if not res.get("success"):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=res.get("message"))
    return res


@router.post("/cross-branch-compare")
async def compare_cross_branch_endpoint(
    body: CompareCrossBranchIn,
    _user: User = Depends(get_current_user),
) -> dict[str, Any]:
    """执行跨分支基线快照差分与演化审计。"""
    _ = _user
    report = compare_cross_branch_baselines(
        page_route=body.page_route,
        source_branch=body.source_branch,
        target_branch=body.target_branch,
    )
    return {"message": "跨分支视觉基线比对完成", "report": report.to_dict()}


@router.get("/list")
async def list_baselines_endpoint(
    page_route: str | None = None,
    branch_name: str | None = None,
    _user: User = Depends(get_current_user),
) -> dict[str, Any]:
    """查询多版本视觉基线快照列表。"""
    _ = _user
    baselines = list_visual_baselines(page_route=page_route, branch_name=branch_name)
    return {"total": len(baselines), "baselines": baselines}


@router.get("/{baseline_id}")
async def get_baseline_endpoint(
    baseline_id: str,
    _user: User = Depends(get_current_user),
) -> dict[str, Any]:
    """查询单条视觉基线快照详情。"""
    _ = _user
    base = get_visual_baseline(baseline_id)
    if not base:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"基线 [{baseline_id}] 不存在")
    return {"baseline": base.to_dict()}


@router.delete("/clear")
async def clear_baselines_endpoint(
    _user: User = Depends(require_engineer),
) -> dict[str, Any]:
    """清空所有视觉基线快照（需工程师权限）。"""
    _ = _user
    clear_baseline_tracker_store()
    return {"message": "已清空所有视觉基线快照"}
