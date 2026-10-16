"""生产全链路压测安全审计与爆炸半径评估 REST API (T4.2)。"""

from __future__ import annotations

from typing import Any
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field

from app.api.deps import get_current_user, require_engineer
from app.models.user import User
from app.services.stress_blast_radius_safety_evaluator import (
    clear_blast_radius_store,
    evaluate_stress_blast_radius_safety,
    get_blast_radius_report,
    list_blast_radius_reports,
)

router = APIRouter(prefix="/stress/drill-report/blast-radius", tags=["压测安全审计与爆炸半径 (T4.2)"])


class EvaluateSafetyIn(BaseModel):
    drill_id: str = Field(default="drill_black_friday_01", description="压测演练计划唯一标识")
    target_services: list[str] = Field(
        default_factory=lambda: ["gateway", "order_service"], description="涉及微服务清单"
    )
    shadow_traffic_isolated: bool = Field(default=True, description="影子流量染色标是否 100% 隔离透传")
    shadow_tables_ready: bool = Field(default=True, description="影子库表防污染隔离是否 100% 就绪")
    external_bypasses_ready: bool = Field(default=True, description="外部短信/支付依赖是否已配置 Mock/Drop 旁路")
    circuit_breaker_active: bool = Field(default=True, description="毫秒级防雪崩自适应熔断器是否在线就绪")
    estimated_max_qps: float = Field(default=2000.0, ge=0.0, description="预估峰值负载 QPS")
    participating_cell_ids: list[str] = Field(
        default_factory=lambda: ["cell_east_01"], description="参与演练的单元 ID 列表"
    )


@router.post("/evaluate")
async def evaluate_safety_endpoint(
    body: EvaluateSafetyIn,
    _user: User = Depends(get_current_user),
) -> dict[str, Any]:
    """全息评估生产全链路压测的潜在爆炸半径与安全准入资质，生成防篡改指纹。"""
    _ = _user
    report = evaluate_stress_blast_radius_safety(
        drill_id=body.drill_id,
        target_services=body.target_services,
        shadow_traffic_isolated=body.shadow_traffic_isolated,
        shadow_tables_ready=body.shadow_tables_ready,
        external_bypasses_ready=body.external_bypasses_ready,
        circuit_breaker_active=body.circuit_breaker_active,
        estimated_max_qps=body.estimated_max_qps,
        participating_cell_ids=body.participating_cell_ids,
    )
    return {"message": "全链路压测爆炸半径评估完成", "report": report.to_dict()}


@router.get("/reports")
async def list_reports_endpoint(
    limit: int = 50,
    _user: User = Depends(get_current_user),
) -> dict[str, Any]:
    """获取历史压测安全准入与爆炸半径评估报告列表。"""
    _ = _user
    reports = list_blast_radius_reports(limit=limit)
    return {"total": len(reports), "reports": reports}


@router.get("/reports/{report_id}")
async def get_report_endpoint(
    report_id: str,
    _user: User = Depends(get_current_user),
) -> dict[str, Any]:
    """按 ID 查询单次爆炸半径评估报告详情。"""
    _ = _user
    report = get_blast_radius_report(report_id)
    if not report:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"报告 [{report_id}] 不存在")
    return {"report": report.to_dict()}


@router.delete("/reports")
async def clear_reports_endpoint(
    _user: User = Depends(require_engineer),
) -> dict[str, Any]:
    """清空爆炸半径报告仓库 (需工程师权限)。"""
    _ = _user
    clear_blast_radius_store()
    return {"message": "已清空所有压测安全准入与爆炸半径报告"}
