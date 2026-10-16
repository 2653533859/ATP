"""跨单元服务依赖逃逸与拓扑孤岛检测 REST API (T2.2)。"""

from __future__ import annotations

from typing import Any
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field

from app.api.deps import get_current_user, require_engineer
from app.models.user import User
from app.services.cell_escape_dependency_detector import (
    clear_cell_escape_store,
    detect_cell_escapes,
    get_cell_escape_report,
    list_cell_escape_reports,
)

router = APIRouter(prefix="/stress/cell-isolation/escape", tags=["单元依赖逃逸与孤岛检测 (T2.2)"])


class InvocationEdgeIn(BaseModel):
    source_cell_id: str = Field(..., description="调用方所在单元 ID (如 cell_east_01)")
    source_service: str = Field(..., description="调用发起方微服务名称")
    target_cell_id: str = Field(..., description="被调方所在单元 ID")
    target_service: str = Field(..., description="目标微服务或存储资源名称")
    target_resource_type: str = Field(
        default="MICROSERVICE_RPC", description="目标类型: MICROSERVICE_RPC, DATABASE, REDIS_CACHE, MESSAGE_QUEUE"
    )
    is_shadow_traffic: bool = Field(default=False, description="是否属于压测影子流量")
    is_shared_resource: bool = Field(default=False, description="是否为跨单元共享资源")


class DetectCellEscapesIn(BaseModel):
    topology_name: str = Field(default="prod_mesh_topology", description="拓扑环境名称")
    invocation_edges: list[InvocationEdgeIn] = Field(..., min_length=1, description="全链路微服务调用边集合")


@router.post("/detect")
async def detect_cell_escapes_endpoint(
    body: DetectCellEscapesIn,
    _user: User = Depends(get_current_user),
) -> dict[str, Any]:
    """深度探查跨单元跨界 RPC、共享资源混用与影子流量逃逸隐患。"""
    _ = _user
    edges_dicts = [e.model_dump() for e in body.invocation_edges]
    report = detect_cell_escapes(
        topology_name=body.topology_name,
        invocation_edges=edges_dicts,
    )
    return {"message": "单元化依赖逃逸检测完成", "report": report.to_dict()}


@router.get("/reports")
async def list_reports_endpoint(
    limit: int = 50,
    _user: User = Depends(get_current_user),
) -> dict[str, Any]:
    """获取历史单元逃逸检测报告列表。"""
    _ = _user
    reports = list_cell_escape_reports(limit=limit)
    return {"total": len(reports), "reports": reports}


@router.get("/reports/{report_id}")
async def get_report_endpoint(
    report_id: str,
    _user: User = Depends(get_current_user),
) -> dict[str, Any]:
    """按 ID 查询单次单元逃逸报告详情。"""
    _ = _user
    report = get_cell_escape_report(report_id)
    if not report:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"报告 [{report_id}] 不存在")
    return {"report": report.to_dict()}


@router.delete("/reports")
async def clear_reports_endpoint(
    _user: User = Depends(require_engineer),
) -> dict[str, Any]:
    """清空单元逃逸报告仓库 (需工程师权限)。"""
    _ = _user
    clear_cell_escape_store()
    return {"message": "已清空所有单元逃逸检测报告"}
