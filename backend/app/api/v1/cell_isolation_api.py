"""单元化架构测试隔离与流量调度控制器 REST API (T2.1)。"""

from __future__ import annotations

from typing import Any
from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field

from app.api.deps import get_current_user, require_engineer
from app.models.user import User
from app.services.cell_based_testing_traffic_controller import (
    CellStatus,
    clear_cell_registry_store,
    generate_cell_topology_report,
    list_cells,
    register_cell,
    route_request_to_cell,
    update_cell_weights,
)

router = APIRouter(prefix="/stress/cell-isolation/routing", tags=["单元化测试切流与隔离调度 (T2.1)"])


class RouteDecisionIn(BaseModel):
    user_id: str | None = Field(default=None, description="用户唯一标识 (用于分片取模)")
    is_shadow_traffic: bool = Field(default=False, description="是否属于压测影子流量")
    headers: dict[str, Any] = Field(default_factory=dict, description="入站请求头")


class RegisterCellIn(BaseModel):
    cell_id: str = Field(..., description="业务单元唯一标识 (如 cell_east_01)")
    cell_name: str = Field(..., description="单元名称")
    zone: str = Field(..., description="所属物理可用区/机房 (如 cn-east-2a)")
    traffic_weight: int = Field(default=50, ge=0, le=100, description="流量权重 0~100")
    status: str = Field(
        default="ACTIVE_PROD", description="生命周期状态: ACTIVE_PROD, STRESS_ONLY, DRAINING, ISOLATED_FAILSAFE"
    )
    allowed_shards: list[int] = Field(default_factory=list, description="负责的用户分片键列表")
    is_stress_target: bool = Field(default=False, description="是否作为专属压测目标单元")


class UpdateWeightsIn(BaseModel):
    weights: dict[str, int] = Field(..., description="单元 ID 到权重的字典映射")


@router.post("/decide")
async def route_decision_endpoint(
    body: RouteDecisionIn,
    _user: User = Depends(get_current_user),
) -> dict[str, Any]:
    """根据入站上下文 (是否影子流量、用户分片、权重) 智能判定目标单元。"""
    _ = _user
    decision = route_request_to_cell(
        user_id=body.user_id,
        is_shadow_traffic=body.is_shadow_traffic,
        headers=body.headers,
    )
    return {"message": "单元化路由决策完成", "decision": decision.to_dict()}


@router.post("/cells")
async def register_cell_endpoint(
    body: RegisterCellIn,
    _user: User = Depends(require_engineer),
) -> dict[str, Any]:
    """注册或更新业务单元拓扑 (需工程师权限)。"""
    _ = _user
    try:
        c_status = CellStatus[body.status.upper()]
    except KeyError:
        c_status = CellStatus.ACTIVE_PROD

    cell = register_cell(
        cell_id=body.cell_id,
        cell_name=body.cell_name,
        zone=body.zone,
        traffic_weight=body.traffic_weight,
        status=c_status,
        allowed_shards=body.allowed_shards,
        is_stress_target=body.is_stress_target,
    )
    return {"message": "业务单元注册成功", "cell": cell.to_dict()}


@router.get("/cells")
async def list_cells_endpoint(
    _user: User = Depends(get_current_user),
) -> dict[str, Any]:
    """获取所有已注册的业务单元拓扑列表。"""
    _ = _user
    cells = list_cells()
    return {"total": len(cells), "cells": cells}


@router.post("/weights")
async def update_weights_endpoint(
    body: UpdateWeightsIn,
    _user: User = Depends(require_engineer),
) -> dict[str, Any]:
    """批量调整单元的流量分流权重 (需工程师权限)。"""
    _ = _user
    updated = update_cell_weights(body.weights)
    return {"message": "单元流量权重更新成功", "cells": updated}


@router.get("/topology")
async def get_topology_endpoint(
    _user: User = Depends(get_current_user),
) -> dict[str, Any]:
    """获取全景单元化拓扑状态报告。"""
    _ = _user
    report = generate_cell_topology_report()
    return {"report": report.to_dict()}


@router.delete("/cells")
async def clear_cells_endpoint(
    _user: User = Depends(require_engineer),
) -> dict[str, Any]:
    """清空重置单元拓扑仓库 (需工程师权限)。"""
    _ = _user
    clear_cell_registry_store()
    return {"message": "已重置单元拓扑仓库为默认状态"}
