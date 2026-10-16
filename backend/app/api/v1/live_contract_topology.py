"""契约漂移下游受影响服务级联拓扑探测与告警 REST API (T3.3)。"""

from __future__ import annotations

from typing import Any
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field

from app.api.deps import get_current_user, require_engineer
from app.models.user import User
from app.services.contract_drift_impact_topology_router import (
    analyze_contract_drift_impact,
    clear_topology_and_reports,
    get_impact_analysis_report,
    get_service_topology,
    list_impact_analysis_reports,
    register_service_dependency,
    register_service_node,
)

router = APIRouter(prefix="/contract-guard/impact-topology", tags=["契约级联影响拓扑路由网关 (T3.3)"])


class AnalyzeCascadeImpactIn(BaseModel):
    endpoint: str = Field(..., description="受损的接口端点 (如 POST /api/v1/orders/checkout)")
    broken_fields: list[str] = Field(
        default_factory=list, description="发生破坏性变更的字段列表 (如 ['amount', 'order_id'])"
    )
    producer_service_id: str | None = Field(default=None, description="提供该接口的微服务 ID (选填)")
    dispatch_alerts: bool = Field(default=True, description="是否向受影响服务的负责人和 Webhook 派发告警")


class RegisterServiceNodeIn(BaseModel):
    service_id: str = Field(..., description="微服务唯一标识 (如 order-service)")
    service_name: str = Field(..., description="微服务名称")
    owner: str = Field(..., description="服务负责人或团队")
    notification_webhook: str | None = Field(default=None, description="告警通知 Webhook URL")
    is_critical_asset: bool = Field(default=False, description="是否属于核心级微服务资产")


class RegisterDependencyIn(BaseModel):
    consumer_service_id: str = Field(..., description="调用方服务 ID (下游)")
    producer_service_id: str = Field(..., description="提供方服务 ID (上游)")
    endpoint: str = Field(..., description="调用的接口端点 (如 POST /api/v1/orders/checkout)")
    consumed_fields: list[str] = Field(default_factory=list, description="下游具体消费的字段列表")
    call_frequency: str = Field(default="HIGH", description="调用频次: HIGH | MEDIUM | LOW")


@router.post("/analyze")
async def analyze_impact_endpoint(
    body: AnalyzeCascadeImpactIn,
    _user: User = Depends(require_engineer),
) -> dict[str, Any]:
    """根据受损接口与字段执行全网微服务级联依赖追溯并路由告警 (需工程师权限)。"""
    _ = _user
    report = analyze_contract_drift_impact(
        endpoint=body.endpoint,
        broken_fields=body.broken_fields,
        producer_service_id=body.producer_service_id,
        dispatch_alerts=body.dispatch_alerts,
    )
    return {"message": "契约破坏级联影响分析完成", "report": report.to_dict()}


@router.get("/topology")
async def get_topology_endpoint(
    _user: User = Depends(get_current_user),
) -> dict[str, Any]:
    """查询当前全网微服务节点与字段级调用依赖拓扑。"""
    _ = _user
    return get_service_topology()


@router.post("/services")
async def register_service_endpoint(
    body: RegisterServiceNodeIn,
    _user: User = Depends(require_engineer),
) -> dict[str, Any]:
    """注册或更新微服务节点 (需工程师权限)。"""
    _ = _user
    node = register_service_node(
        service_id=body.service_id,
        service_name=body.service_name,
        owner=body.owner,
        notification_webhook=body.notification_webhook,
        is_critical_asset=body.is_critical_asset,
    )
    return {"message": "微服务节点已注册", "service": node.to_dict()}


@router.post("/dependencies")
async def register_dependency_endpoint(
    body: RegisterDependencyIn,
    _user: User = Depends(require_engineer),
) -> dict[str, Any]:
    """注册微服务间接口依赖调用边与消费字段 (需工程师权限)。"""
    _ = _user
    edge = register_service_dependency(
        consumer_service_id=body.consumer_service_id,
        producer_service_id=body.producer_service_id,
        endpoint=body.endpoint,
        consumed_fields=body.consumed_fields,
        call_frequency=body.call_frequency,
    )
    return {"message": "服务调用依赖已注册", "dependency": edge.to_dict()}


@router.get("/reports")
async def list_reports_endpoint(
    _user: User = Depends(get_current_user),
) -> dict[str, Any]:
    """查询历史契约级联影响分析报告列表。"""
    _ = _user
    reports = list_impact_analysis_reports()
    return {"total": len(reports), "reports": [r.to_dict() for r in reports]}


@router.get("/reports/{analysis_id}")
async def get_report_endpoint(
    analysis_id: str,
    _user: User = Depends(get_current_user),
) -> dict[str, Any]:
    """获取指定契约级联影响分析报告详情。"""
    _ = _user
    report = get_impact_analysis_report(analysis_id)
    if not report:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"分析报告不存在: {analysis_id}")
    return report.to_dict()


@router.delete("/topology")
async def clear_topology_endpoint(
    _user: User = Depends(require_engineer),
) -> dict[str, Any]:
    """重置微服务依赖拓扑与报告为出厂基线 (需工程师权限)。"""
    _ = _user
    clear_topology_and_reports()
    return {"message": "微服务依赖拓扑与报告已重置为出厂基准"}
