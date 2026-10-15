"""Microservice Mesh Chaos Fault Injection and Orchestration REST API (T3.1)."""

from __future__ import annotations

from typing import Any
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from app.api.deps import get_current_user, require_engineer
from app.models.user import User
from app.services.mesh_chaos_orchestrator import (
    create_chaos_experiment,
    evaluate_mesh_request,
    get_chaos_experiment,
    list_chaos_experiments,
    set_experiment_status,
)

router = APIRouter(prefix="/mesh-chaos", tags=["分布式微服务网关混沌演练"])


class ChaosRuleIn(BaseModel):
    service_name: str = Field(default="*", description="目标微服务名称 (如 order-service)")
    route_pattern: str = Field(default=".*", description="匹配 URL 正则表达式")
    action: str = Field(
        ..., description="故障动作 (service_down_503, circuit_breaker_trip, latency_jitter, corrupt_payload)"
    )
    traffic_ratio: float = Field(default=1.0, ge=0.0, le=1.0, description="流量抽样比例")
    methods: list[str] = Field(default_factory=lambda: ["*"])
    header_matchers: dict[str, str] = Field(default_factory=dict)
    action_params: dict[str, Any] = Field(default_factory=dict)
    enabled: bool = True


class CreateChaosExperimentIn(BaseModel):
    name: str = Field(min_length=1, max_length=128)
    description: str = Field(default="")
    rules: list[ChaosRuleIn] = Field(min_length=1)


class SetStatusIn(BaseModel):
    status: str = Field(..., description="active | paused | completed")


class EvaluateMeshRequestIn(BaseModel):
    service_name: str
    path: str
    method: str = "GET"
    headers: dict[str, str] = Field(default_factory=dict)


@router.post("/experiments")
async def create_experiment_endpoint(
    body: CreateChaosExperimentIn,
    _user: User = Depends(require_engineer),
):
    """创建并注册新的微服务网关混沌故障实验。"""
    try:
        rules_dicts = [r.model_dump() for r in body.rules]
        exp = create_chaos_experiment(
            name=body.name,
            rules_data=rules_dicts,
            description=body.description,
        )
        return exp.to_dict()
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@router.get("/experiments")
async def list_experiments_endpoint(
    _user: User = Depends(get_current_user),
):
    """获取全量微服务混沌演练实验列表与实时命中统计。"""
    return list_chaos_experiments()


@router.get("/experiments/{experiment_id}")
async def get_experiment_endpoint(
    experiment_id: str,
    _user: User = Depends(get_current_user),
):
    """获取单个混沌演练实验的详细配置与运行指标。"""
    exp = get_chaos_experiment(experiment_id)
    if not exp:
        raise HTTPException(status_code=404, detail="混沌实验不存在")
    return exp.to_dict()


@router.post("/experiments/{experiment_id}/status")
async def set_experiment_status_endpoint(
    experiment_id: str,
    body: SetStatusIn,
    _user: User = Depends(require_engineer),
):
    """修改混沌演练实验状态 (active / paused / completed)。"""
    try:
        ok = set_experiment_status(experiment_id, body.status)
        if not ok:
            raise HTTPException(status_code=404, detail="混沌实验不存在")
        return {"experiment_id": experiment_id, "status": body.status}
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@router.post("/evaluate")
async def evaluate_mesh_request_endpoint(
    body: EvaluateMeshRequestIn,
    _user: User = Depends(get_current_user),
):
    """评估网关/微服务请求是否命中混沌规则，并返回具体故障注入决策。"""
    decision = evaluate_mesh_request(
        service_name=body.service_name,
        path=body.path,
        method=body.method,
        headers=body.headers,
    )
    return decision.to_dict()
