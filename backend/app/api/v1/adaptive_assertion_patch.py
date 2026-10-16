"""接口响应变迁自适应断言规则推导与自动打补丁 REST API (T4.2)。"""

from __future__ import annotations

from typing import Any
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field

from app.api.deps import get_current_user, require_engineer
from app.models.user import User
from app.services.adaptive_assertion_auto_patcher import (
    apply_assertion_patch,
    clear_assertion_patch_store,
    derive_adaptive_assertion_patch,
    list_assertion_patches,
)

router = APIRouter(prefix="/healing/assertion-patch", tags=["自适应断言规则与自动补丁 (T4.2)"])


class DerivePatchIn(BaseModel):
    case_id: str = Field(..., description="关联用例 ID")
    original_assertion: str = Field(..., description="失效的原断言表达式 (如 $.order_id == 101)")
    actual_response_payload: Any = Field(..., description="实测真实响应体 (dict / list / str)")
    endpoint: str = Field(default="POST /api/v1/orders/checkout", description="接口端点")
    expected_value: Any = Field(default=None, description="断言期望比较的右值")


@router.post("/derive")
async def derive_patch_endpoint(
    body: DerivePatchIn,
    _user: User = Depends(get_current_user),
) -> dict[str, Any]:
    """根据失效断言与实际响应逆向推导自愈断言表达式与 Python 代码补丁。"""
    _ = _user
    patch = derive_adaptive_assertion_patch(
        case_id=body.case_id,
        original_assertion=body.original_assertion,
        actual_response_payload=body.actual_response_payload,
        endpoint=body.endpoint,
        expected_value=body.expected_value,
    )
    return {"message": "自适应断言补丁推导成功", "patch": patch.to_dict()}


@router.post("/apply/{patch_id}")
async def apply_patch_endpoint(
    patch_id: str,
    _user: User = Depends(require_engineer),
) -> dict[str, Any]:
    """一键持久化应用生效断言自愈补丁 (需工程师权限)。"""
    _ = _user
    ok = apply_assertion_patch(patch_id)
    if not ok:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"未找到该断言补丁: {patch_id}",
        )
    return {"message": "断言补丁已持久化应用生效", "patch_id": patch_id}


@router.get("/patches")
async def list_patches_endpoint(
    case_id: str | None = None,
    patch_type: str | None = None,
    _user: User = Depends(get_current_user),
) -> dict[str, Any]:
    """查询已推导的断言自愈补丁清单。"""
    _ = _user
    patches = list_assertion_patches(case_id=case_id, patch_type=patch_type)
    return {"total": len(patches), "patches": [p.to_dict() for p in patches]}


@router.delete("/patches")
async def clear_patches_endpoint(
    _user: User = Depends(require_engineer),
) -> dict[str, Any]:
    """清空断言自愈补丁仓库 (需工程师权限)。"""
    _ = _user
    c = clear_assertion_patch_store()
    return {"message": f"已清空 {c} 条断言补丁记录", "cleared_count": c}
