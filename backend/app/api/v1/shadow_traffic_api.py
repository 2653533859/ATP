"""全链路影子流量染色与透传校验 REST API (T1.1)。"""

from __future__ import annotations

from typing import Any
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field

from app.api.deps import get_current_user, require_engineer
from app.models.user import User
from app.services.shadow_traffic_taint_propagator import (
    ProtocolType,
    clear_shadow_taint_store,
    get_shadow_taint_report,
    inject_shadow_taint,
    list_shadow_taint_reports,
    verify_trace_propagation,
)

router = APIRouter(prefix="/stress/shadow-traffic/taint", tags=["影子流量染色透传 (T1.1)"])


class InjectTaintIn(BaseModel):
    protocol: str = Field(
        default="HTTP_REST", description="通信协议类型: HTTP_REST, GRPC, KAFKA_MQ, RABBITMQ, ROCKETMQ"
    )
    headers: dict[str, Any] = Field(default_factory=dict, description="原始请求头/元数据字典")
    trace_id: str | None = Field(default=None, description="自定义影子链路唯一标识")
    cluster_tag: str = Field(default="prod_stress_01", description="压测机集群集群标签")


class ServiceHopIn(BaseModel):
    service_name: str = Field(..., description="服务节点名称")
    protocol: str = Field(default="HTTP_REST", description="通信协议")
    headers: dict[str, Any] = Field(default_factory=dict, description="该节点收到的头部字典")


class VerifyPropagationIn(BaseModel):
    trace_id: str = Field(..., description="待核验的影子链路 ID")
    hop_traces: list[ServiceHopIn] = Field(..., min_length=1, description="全链路各跳节点追踪快照")


@router.post("/inject")
async def inject_taint_endpoint(
    body: InjectTaintIn,
    _user: User = Depends(get_current_user),
) -> dict[str, Any]:
    """对指定通信协议载荷动态注入生产级影子流量染色标头。"""
    _ = _user
    try:
        prot = ProtocolType[body.protocol.upper()]
    except KeyError:
        prot = ProtocolType.HTTP_REST

    injected = inject_shadow_taint(
        protocol=prot,
        payload_headers=body.headers,
        trace_id=body.trace_id,
        cluster_tag=body.cluster_tag,
    )
    return {
        "message": "影子流量染色标头已注入",
        "protocol": prot.value,
        "injected_headers": injected,
    }


@router.post("/verify-propagation")
async def verify_propagation_endpoint(
    body: VerifyPropagationIn,
    _user: User = Depends(get_current_user),
) -> dict[str, Any]:
    """深度校验端到端微服务多跳拓扑中的影子染色标完整性。"""
    _ = _user
    hops_dicts = [h.model_dump() for h in body.hop_traces]
    report = verify_trace_propagation(
        trace_id=body.trace_id,
        hop_traces=hops_dicts,
    )
    return {"message": "影子流量染色透传校验完成", "report": report.to_dict()}


@router.get("/reports")
async def list_reports_endpoint(
    limit: int = 50,
    _user: User = Depends(get_current_user),
) -> dict[str, Any]:
    """获取历史影子流量染色透传校验报告列表。"""
    _ = _user
    reports = list_shadow_taint_reports(limit=limit)
    return {"total": len(reports), "reports": reports}


@router.get("/reports/{report_id}")
async def get_report_endpoint(
    report_id: str,
    _user: User = Depends(get_current_user),
) -> dict[str, Any]:
    """按 ID 查询单次染色透传校验报告详情。"""
    _ = _user
    report = get_shadow_taint_report(report_id)
    if not report:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"报告 [{report_id}] 不存在")
    return {"report": report.to_dict()}


@router.delete("/reports")
async def clear_reports_endpoint(
    _user: User = Depends(require_engineer),
) -> dict[str, Any]:
    """清空影子染色校验报告仓库 (需工程师权限)。"""
    _ = _user
    clear_shadow_taint_store()
    return {"message": "已清空所有影子染色校验报告"}
