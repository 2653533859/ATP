"""接口契约字段级兼容性差分与 Breaking 破坏性评级 REST API (T3.2)。"""

from __future__ import annotations

from typing import Any
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field

from app.api.deps import get_current_user, require_engineer
from app.models.user import User
from app.services.contract_drift_breaking_evaluator import (
    clear_drift_evaluation_reports,
    evaluate_contract_drift,
    get_drift_evaluation_report,
    list_drift_evaluation_reports,
)
from app.services.live_contract_schema_extractor import get_extracted_contract

router = APIRouter(prefix="/contract-guard/evaluate", tags=["接口契约破坏性变更评级引擎 (T3.2)"])


class CompareContractDriftIn(BaseModel):
    design_contract: dict[str, Any] = Field(..., description="设计期或基准期 API 契约定义")
    live_contract: dict[str, Any] = Field(..., description="现网生产流量逆向推导的 API 契约定义")
    endpoint: str | None = Field(default=None, description="接口端点标识 (如 POST /api/v1/orders/checkout)")


class CompareByContractIdsIn(BaseModel):
    design_contract_id: str = Field(..., description="设计期/基准期契约 ID")
    live_contract_id: str = Field(..., description="现网推导契约 ID")


@router.post("/compare")
async def evaluate_contract_drift_endpoint(
    body: CompareContractDriftIn,
    _user: User = Depends(get_current_user),
) -> dict[str, Any]:
    """对比设计期契约与现网流量契约，执行非对称破坏性变更评级 (BREAKING / WARNING / COMPATIBLE)。"""
    _ = _user
    report = evaluate_contract_drift(
        design_contract=body.design_contract,
        live_contract=body.live_contract,
        endpoint=body.endpoint,
    )
    return {"message": "契约兼容性评估完成", "report": report.to_dict()}


@router.post("/by-contract-ids")
async def evaluate_by_contract_ids_endpoint(
    body: CompareByContractIdsIn,
    _user: User = Depends(get_current_user),
) -> dict[str, Any]:
    """根据两个已提取或录入的契约 ID 执行破坏性变更评级。"""
    _ = _user
    d_contract = get_extracted_contract(body.design_contract_id)
    if not d_contract:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=f"设计期基准契约不存在: {body.design_contract_id}"
        )

    l_contract = get_extracted_contract(body.live_contract_id)
    if not l_contract:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=f"现网推导契约不存在: {body.live_contract_id}"
        )

    report = evaluate_contract_drift(
        design_contract=d_contract,
        live_contract=l_contract,
    )
    return {"message": "契约兼容性评估完成", "report": report.to_dict()}


@router.get("/reports")
async def list_reports_endpoint(
    _user: User = Depends(get_current_user),
) -> dict[str, Any]:
    """查询历史契约破坏性变更评估报告列表。"""
    _ = _user
    reports = list_drift_evaluation_reports()
    return {"total": len(reports), "reports": [r.to_dict() for r in reports]}


@router.get("/reports/{evaluation_id}")
async def get_report_endpoint(
    evaluation_id: str,
    _user: User = Depends(get_current_user),
) -> dict[str, Any]:
    """获取指定契约破坏性评估报告详情。"""
    _ = _user
    report = get_drift_evaluation_report(evaluation_id)
    if not report:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"评估报告不存在: {evaluation_id}")
    return report.to_dict()


@router.delete("/reports")
async def clear_reports_endpoint(
    _user: User = Depends(require_engineer),
) -> dict[str, Any]:
    """清空契约评估报告缓存 (需工程师权限)。"""
    _ = _user
    count = clear_drift_evaluation_reports()
    return {"message": f"已清空 {count} 条评估报告", "deleted_count": count}
