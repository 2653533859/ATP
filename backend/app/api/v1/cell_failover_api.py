"""单元故障演练与常态化容灾接管 REST API (T2.3)。"""

from __future__ import annotations

from typing import Any
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field

from app.api.deps import get_current_user, require_engineer
from app.models.user import User
from app.services.cell_failover_resilience_verifier import (
    clear_failover_report_store,
    execute_cell_failover_drill,
    get_failover_report,
    list_failover_reports,
)

router = APIRouter(prefix="/stress/cell-isolation/failover", tags=["单元容灾切流与自愈 (T2.3)"])


class SimulateFailoverIn(BaseModel):
    failed_cell_id: str = Field(default="cell_east_01", description="模拟故障的源单元 ID")
    standby_cell_id: str = Field(default="cell_east_02", description="承接流量的备用单元 ID")
    traffic_shift_percentage: float = Field(default=100.0, ge=1.0, le=100.0, description="切流比例 1~100%")
    dns_switch_delay_ms: float = Field(default=650.0, description="DNS/网关切流延迟 ms")
    db_replication_lag_ms: float = Field(default=180.0, description="数据副本追平耗时 ms")
    route_convergence_delay_ms: float = Field(default=420.0, description="微服务网格路由收敛耗时 ms")


@router.post("/simulate")
async def simulate_failover_endpoint(
    body: SimulateFailoverIn,
    _user: User = Depends(get_current_user),
) -> dict[str, Any]:
    """模拟单单元整体瘫痪，量化备用单元自动接管耗时 (RTO)、流量丢包率与自愈状态。"""
    _ = _user
    report = execute_cell_failover_drill(
        failed_cell_id=body.failed_cell_id,
        standby_cell_id=body.standby_cell_id,
        traffic_shift_percentage=body.traffic_shift_percentage,
        dns_switch_delay_ms=body.dns_switch_delay_ms,
        db_replication_lag_ms=body.db_replication_lag_ms,
        route_convergence_delay_ms=body.route_convergence_delay_ms,
    )
    return {"message": "单元容灾切流演练完成", "report": report.to_dict()}


@router.get("/reports")
async def list_reports_endpoint(
    limit: int = 50,
    _user: User = Depends(get_current_user),
) -> dict[str, Any]:
    """获取历史单元容灾切流演练报告列表。"""
    _ = _user
    reports = list_failover_reports(limit=limit)
    return {"total": len(reports), "reports": reports}


@router.get("/reports/{report_id}")
async def get_report_endpoint(
    report_id: str,
    _user: User = Depends(get_current_user),
) -> dict[str, Any]:
    """按 ID 查询单次容灾演练报告详情。"""
    _ = _user
    report = get_failover_report(report_id)
    if not report:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"报告 [{report_id}] 不存在")
    return {"report": report.to_dict()}


@router.delete("/reports")
async def clear_reports_endpoint(
    _user: User = Depends(require_engineer),
) -> dict[str, Any]:
    """清空单元容灾切流演练报告仓库 (需工程师权限)。"""
    _ = _user
    clear_failover_report_store()
    return {"message": "已清空所有单元容灾切流演练报告"}
