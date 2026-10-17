"""自动化测试用例自愈与断言演进 REST API (T1.3)

为 UI 与接口自动化测试提供失败拦截、定位器动态自愈与补丁生命周期管理:
1. 定位失效多模态自愈诊断 (/self-healing/locator/diagnose);
2. 运行时现场热替换自愈执行 (/self-healing/locator/heal);
3. 自愈补丁采纳与回滚控制 (/self-healing/patch/{patch_id}/commit, /reject);
4. 补丁详情与历史检索 (/self-healing/patch/{patch_id}, /self-healing/patches)。
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from app.api.deps import require_engineer
from app.models.user import User
from app.services.dynamic_locator_self_healer import (
    BrokenLocatorContext,
    CandidateDOMNode,
    derive_self_healing_candidates,
)
from app.services.runtime_healing_patcher import (
    commit_healing_patch,
    get_healing_patch,
    intercept_and_heal_step,
    list_healing_patches,
    reject_healing_patch,
)

router = APIRouter(prefix="/self-healing", tags=["Test Self-Healing & Assertion Evolution"])


class DiagnoseLocatorRequest(BaseModel):
    step_id: str = Field(..., description="失败步骤 ID")
    failed_locator_type: str = Field("css", description="失效定位器类型 (css | id | xpath)")
    failed_locator_value: str = Field(..., description="失效定位器表达式")
    element_text_hint: Optional[str] = Field(None, description="期望文案提示")
    element_role_hint: Optional[str] = Field("button", description="期望控件角色")
    screen_nodes: List[Dict[str, Any]] = Field(..., description="当前屏幕活体 DOM / UI 节点列表")
    confidence_threshold: float = Field(0.65, ge=0.0, le=1.0, description="自愈置信度门限")


class HealStepRequest(BaseModel):
    step_id: str = Field(..., description="失败步骤 ID")
    failed_locator_type: str = Field("css", description="失效定位器类型")
    failed_locator_value: str = Field(..., description="失效定位器表达式")
    element_text_hint: Optional[str] = Field(None, description="期望文案提示")
    element_role_hint: Optional[str] = Field("button", description="期望角色")
    screen_nodes: List[Dict[str, Any]] = Field(..., description="当前屏幕活体 DOM 节点")
    case_id: Optional[str] = Field(None, description="所属用例 ID")
    platform: str = Field("web", description="执行平台 (web | ios | android)")
    confidence_threshold: float = Field(0.65, ge=0.0, le=1.0, description="自愈门限")


@router.post("/locator/diagnose")
def diagnose_locator_endpoint(
    payload: DiagnoseLocatorRequest,
    _user: User = Depends(require_engineer),
) -> Dict[str, Any]:
    """对定位器失效场景进行多模态分析并推导演算自愈候选"""
    context = BrokenLocatorContext(
        step_id=payload.step_id,
        failed_locator_type=payload.failed_locator_type,
        failed_locator_value=payload.failed_locator_value,
        element_text_hint=payload.element_text_hint,
        element_role_hint=payload.element_role_hint,
    )

    nodes = [
        CandidateDOMNode(
            node_id=n.get("node_id", f"node_{i}"),
            tag_name=n.get("tag_name", "button"),
            text=n.get("text"),
            attributes=n.get("attributes", {}),
            bounding_box=n.get("bounding_box"),
            xpath=n.get("xpath"),
        )
        for i, n in enumerate(payload.screen_nodes)
    ]

    res = derive_self_healing_candidates(context, nodes, payload.confidence_threshold)
    return {
        "message": f"定位器自愈诊断完成，推导出 {len(res.all_candidates)} 项自愈候选",
        "diagnosis": res.to_dict(),
    }


@router.post("/locator/heal")
def heal_step_endpoint(
    payload: HealStepRequest,
    _user: User = Depends(require_engineer),
) -> Dict[str, Any]:
    """运行时拦截失败步骤并执行现场热替换自愈重试"""
    context = BrokenLocatorContext(
        step_id=payload.step_id,
        failed_locator_type=payload.failed_locator_type,
        failed_locator_value=payload.failed_locator_value,
        element_text_hint=payload.element_text_hint,
        element_role_hint=payload.element_role_hint,
    )

    nodes = [
        CandidateDOMNode(
            node_id=n.get("node_id", f"node_{i}"),
            tag_name=n.get("tag_name", "button"),
            text=n.get("text"),
            attributes=n.get("attributes", {}),
            bounding_box=n.get("bounding_box"),
            xpath=n.get("xpath"),
        )
        for i, n in enumerate(payload.screen_nodes)
    ]

    exec_res = intercept_and_heal_step(
        context=context,
        screen_nodes=nodes,
        case_id=payload.case_id,
        platform=payload.platform,
        confidence_threshold=payload.confidence_threshold,
    )

    return {
        "message": exec_res.message,
        "result": exec_res.to_dict(),
    }


@router.post("/patch/{patch_id}/commit")
def commit_patch_endpoint(
    patch_id: str,
    _user: User = Depends(require_engineer),
) -> Dict[str, Any]:
    """确认采纳自愈补丁并永久固化回写至用例库"""
    success = commit_healing_patch(patch_id)
    if not success:
        raise HTTPException(status_code=404, detail="未找到目标自愈补丁")
    patch = get_healing_patch(patch_id)
    return {
        "message": f"自愈补丁 [{patch_id}] 已永久采纳生效！",
        "patch": patch.to_dict() if patch else None,
    }


@router.post("/patch/{patch_id}/reject")
def reject_patch_endpoint(
    patch_id: str,
    _user: User = Depends(require_engineer),
) -> Dict[str, Any]:
    """人工否决或回滚自愈补丁"""
    success = reject_healing_patch(patch_id)
    if not success:
        raise HTTPException(status_code=404, detail="未找到目标自愈补丁")
    return {"message": f"自愈补丁 [{patch_id}] 已被否决回滚"}


@router.get("/patch/{patch_id}")
def get_patch_endpoint(
    patch_id: str,
    _user: User = Depends(require_engineer),
) -> Dict[str, Any]:
    """查询单张自愈补丁详细信息"""
    patch = get_healing_patch(patch_id)
    if not patch:
        raise HTTPException(status_code=404, detail="自愈补丁不存在")
    return {"patch": patch.to_dict()}


@router.get("/patches")
def list_patches_endpoint(
    status: Optional[str] = None,
    limit: int = 50,
    _user: User = Depends(require_engineer),
) -> Dict[str, Any]:
    """查询自愈补丁历史流水列表"""
    patches = list_healing_patches(status=status, limit=limit)
    return {
        "total": len(patches),
        "patches": patches,
    }
