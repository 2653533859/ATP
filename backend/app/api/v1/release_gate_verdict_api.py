"""自动化发版准入阻断裁决器与豁免网关 REST API (T4.2)。"""

from __future__ import annotations

from typing import Any
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field

from app.api.deps import get_current_user, require_admin, require_engineer
from app.models.user import User
from app.services.smart_release_go_no_go_decider import (
    clear_release_gate_store,
    evaluate_release_gate,
    get_release_gate_record,
    grant_risk_waiver,
    list_release_gate_records,
    revoke_risk_waiver,
)

router = APIRouter(prefix="/gatekeeper/release-verdict", tags=["智能发版准入门禁 (T4.2)"])


class EvaluateVerdictIn(BaseModel):
    target_version: str = Field(default="v4.2.0", description="发版目标版本")
    quality_score: float = Field(..., ge=0.0, le=100.0, description="综合质量得分")
    p0_defects_count: int = Field(default=0, ge=0)
    p1_defects_count: int = Field(default=0, ge=0)
    critical_security_flaws_count: int = Field(default=0, ge=0)
    test_pass_rate_pct: float = Field(default=100.0, ge=0.0, le=100.0)


class GrantWaiverIn(BaseModel):
    waiver_reason: str = Field(..., min_length=5, description="申请特批放行原因说明")
    rollback_plan: str = Field(..., min_length=5, description="故障应急快速回滚方案")


@router.post("/evaluate")
async def evaluate_release_verdict_endpoint(
    body: EvaluateVerdictIn,
    _user: User = Depends(get_current_user),
) -> dict[str, Any]:
    """评估发版门禁指标，输出 GO / CAUTION / NO_GO 准入裁决。"""
    _ = _user
    record = evaluate_release_gate(
        target_version=body.target_version,
        quality_score=body.quality_score,
        p0_defects_count=body.p0_defects_count,
        p1_defects_count=body.p1_defects_count,
        critical_security_flaws_count=body.critical_security_flaws_count,
        test_pass_rate_pct=body.test_pass_rate_pct,
    )
    return {"message": "发版质量准入门禁评估完成", "record": record.to_dict()}


@router.post("/{release_id}/waive")
async def grant_waiver_endpoint(
    release_id: str,
    body: GrantWaiverIn,
    user: User = Depends(require_admin),
) -> dict[str, Any]:
    """对阻断的 NO_GO 发版申请签署风险特批豁免（需管理员/架构师权限）。"""
    res = grant_risk_waiver(
        release_id=release_id,
        approver=user.username or "chief_architect",
        waiver_reason=body.waiver_reason,
        rollback_plan=body.rollback_plan,
    )
    if not res.get("success"):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=res.get("message"))
    return res


@router.post("/{release_id}/revoke-waiver")
async def revoke_waiver_endpoint(
    release_id: str,
    _user: User = Depends(require_admin),
) -> dict[str, Any]:
    """撤销已签署的发版风险特批豁免（需管理员/架构师权限）。"""
    _ = _user
    res = revoke_risk_waiver(release_id=release_id)
    if not res.get("success"):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=res.get("message"))
    return res


@router.get("/records")
async def list_records_endpoint(
    limit: int = 50,
    _user: User = Depends(get_current_user),
) -> dict[str, Any]:
    """获取历史发版准入记录列表。"""
    _ = _user
    records = list_release_gate_records(limit=limit)
    return {"total": len(records), "records": records}


@router.get("/records/{release_id}")
async def get_record_endpoint(
    release_id: str,
    _user: User = Depends(get_current_user),
) -> dict[str, Any]:
    """查询单次发版准入裁决与豁免详情。"""
    _ = _user
    record = get_release_gate_record(release_id)
    if not record:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"发版记录 [{release_id}] 不存在")
    return {"record": record.to_dict()}


@router.delete("/records")
async def clear_records_endpoint(
    _user: User = Depends(require_engineer),
) -> dict[str, Any]:
    """清空发版准入记录（需工程师权限）。"""
    _ = _user
    clear_release_gate_store()
    return {"message": "已清空所有发版准入记录"}
