"""生产防击穿自适应分级限流与熔断保护 REST API (T3.3)。"""

from __future__ import annotations

from typing import Any
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field

from app.api.deps import get_current_user, require_engineer
from app.models.user import User
from app.services.adaptive_avalanche_circuit_breaker import (
    clear_avalanche_breaker_store,
    evaluate_adaptive_circuit_breaker,
    get_avalanche_breaker_report,
    get_current_breaker_state,
    list_avalanche_breaker_reports,
    reset_circuit_breaker,
)

router = APIRouter(prefix="/stress/bottleneck-guardian/circuit-breaker", tags=["防雪崩熔断大脑 (T3.3)"])


class EvaluateBreakerIn(BaseModel):
    scenario_name: str = Field(default="stress_checkout_drill", description="压测场景名称")
    max_resource_watermark_pct: float = Field(..., ge=0.0, le=100.0, description="下游基础设施最高水位百分比")
    p99_latency_ms: float = Field(default=120.0, ge=0.0, description="P99 长尾调用时延 ms")
    error_rate_pct: float = Field(default=0.0, ge=0.0, le=100.0, description="系统请求错误率百分比")
    current_tps: float = Field(default=2000.0, ge=0.0, description="当前压测瞬时吞吐量 TPS")


@router.post("/evaluate")
async def evaluate_breaker_endpoint(
    body: EvaluateBreakerIn,
    _user: User = Depends(get_current_user),
) -> dict[str, Any]:
    """自适应评估基础设施与调用链指标，执行毫秒级分级限流与防雪崩熔断判定。"""
    _ = _user
    report = evaluate_adaptive_circuit_breaker(
        scenario_name=body.scenario_name,
        max_resource_watermark_pct=body.max_resource_watermark_pct,
        p99_latency_ms=body.p99_latency_ms,
        error_rate_pct=body.error_rate_pct,
        current_tps=body.current_tps,
    )
    return {"message": "防雪崩分级熔断判定完成", "report": report.to_dict()}


@router.post("/reset")
async def reset_breaker_endpoint(
    _user: User = Depends(require_engineer),
) -> dict[str, Any]:
    """手动强制重置熔断器状态为正常闭合状态 (需工程师权限)。"""
    _ = _user
    state = reset_circuit_breaker()
    return {"message": "自适应熔断器已重置为正常闭合状态", "current_state": state.value}


@router.get("/status")
async def get_status_endpoint(
    _user: User = Depends(get_current_user),
) -> dict[str, Any]:
    """获取当前全局熔断器实时运行状态。"""
    _ = _user
    state = get_current_breaker_state()
    return {"current_state": state.value}


@router.get("/reports")
async def list_reports_endpoint(
    limit: int = 50,
    _user: User = Depends(get_current_user),
) -> dict[str, Any]:
    """获取历史防雪崩熔断评估报告列表。"""
    _ = _user
    reports = list_avalanche_breaker_reports(limit=limit)
    return {"total": len(reports), "reports": reports}


@router.get("/reports/{report_id}")
async def get_report_endpoint(
    report_id: str,
    _user: User = Depends(get_current_user),
) -> dict[str, Any]:
    """按 ID 查询单次熔断评估报告详情。"""
    _ = _user
    report = get_avalanche_breaker_report(report_id)
    if not report:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"报告 [{report_id}] 不存在")
    return {"report": report.to_dict()}


@router.delete("/reports")
async def clear_reports_endpoint(
    _user: User = Depends(require_engineer),
) -> dict[str, Any]:
    """清空熔断报告仓库 (需工程师权限)。"""
    _ = _user
    clear_avalanche_breaker_store()
    return {"message": "已清空所有防雪崩熔断报告"}
