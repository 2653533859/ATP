"""服务断路器与 RTO 恢复指标量化 REST API (T4.2)。"""

from __future__ import annotations

from typing import Any
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field

from app.api.deps import get_current_user, require_engineer
from app.models.user import User
from app.services.resilience_rto_recovery_evaluator import (
    analyze_resilience_rto,
    clear_rto_reports,
    get_rto_report,
    list_rto_reports,
    simulate_circuit_breaker_exercise,
)

router = APIRouter(prefix="/chaos-traffic/evaluate-rto", tags=["断路器与RTO恢复量化器 (T4.2)"])


class AnalyzeRtoIn(BaseModel):
    target_service_id: str = Field(..., description="演练目标微服务 ID (如 order-service)")
    endpoint: str = Field(..., description="接口端点 (如 POST /api/v1/orders/checkout)")
    sample_points: list[dict[str, Any]] = Field(..., min_length=1, description="混沌演练时序采样点数据流")
    expected_fallback_status: int = Field(default=200, description="降级响应预期的 HTTP 状态码")


class SimulateRtoIn(BaseModel):
    target_service_id: str = Field(default="order-service", description="目标微服务 ID")
    endpoint: str = Field(default="POST /api/v1/orders/checkout", description="接口端点")
    tier_preset: str = Field(
        default="EXCELLENT", description="仿真等级预设: EXCELLENT | ADEQUATE | INSUFFICIENT | FRAGILE"
    )


@router.post("/analyze")
async def analyze_rto_endpoint(
    body: AnalyzeRtoIn,
    _user: User = Depends(require_engineer),
) -> dict[str, Any]:
    """对混沌演练采集的时序采样流执行断路器跳闸时延、降级率与 RTO 自愈时长精准度量 (需工程师权限)。"""
    _ = _user
    report = analyze_resilience_rto(
        target_service_id=body.target_service_id,
        endpoint=body.endpoint,
        sample_points=body.sample_points,
        expected_fallback_status=body.expected_fallback_status,
    )
    return {"message": "断路器生效时延与 RTO 恢复指标分析完成", "report": report.to_dict()}


@router.post("/simulate")
async def simulate_rto_endpoint(
    body: SimulateRtoIn,
    _user: User = Depends(get_current_user),
) -> dict[str, Any]:
    """仿真模拟演练一组断路器熔断跳闸与自愈时序流并产出量化报告。"""
    _ = _user
    report = simulate_circuit_breaker_exercise(
        target_service_id=body.target_service_id,
        endpoint=body.endpoint,
        tier_preset=body.tier_preset,
    )
    return {"message": "断路器仿真演练评估完成", "report": report.to_dict()}


@router.get("/reports")
async def list_reports_endpoint(
    _user: User = Depends(get_current_user),
) -> dict[str, Any]:
    """查询历史断路器与 RTO 韧性评估报告列表。"""
    _ = _user
    reports = list_rto_reports()
    return {"total": len(reports), "reports": [r.to_dict() for r in reports]}


@router.get("/reports/{report_id}")
async def get_report_endpoint(
    report_id: str,
    _user: User = Depends(get_current_user),
) -> dict[str, Any]:
    """获取指定 RTO 韧性评估报告详情。"""
    _ = _user
    report = get_rto_report(report_id)
    if not report:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"RTO 韧性报告未找到: {report_id}")
    return report.to_dict()


@router.delete("/reports")
async def clear_reports_endpoint(
    _user: User = Depends(require_engineer),
) -> dict[str, Any]:
    """清空 RTO 韧性报告缓存 (需工程师权限)。"""
    _ = _user
    count = clear_rto_reports()
    return {"message": f"已清空 {count} 条 RTO 报告记录", "deleted_count": count}
