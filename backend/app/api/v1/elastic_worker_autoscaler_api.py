"""云原生动态 Worker 弹性扩缩容与集群配额仲裁 REST API (T1.1)。"""

from __future__ import annotations

from typing import Any
from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field

from app.api.deps import get_current_user, require_engineer
from app.models.user import User
from app.services.elastic_test_worker_autoscaler import (
    ClusterQuotaConfig,
    apply_autoscaling_decision,
    clear_autoscaler_state,
    evaluate_autoscaling,
    get_current_cluster_status,
    list_scaling_events,
)

router = APIRouter(prefix="/cluster/autoscaler", tags=["云原生 Worker 弹性扩缩容 (T1.1)"])


class EvaluateScalingIn(BaseModel):
    queue_depth: int = Field(..., ge=0, description="当前用例执行任务队列排队深度")
    current_replicas: int | None = Field(default=None, ge=1, description="当前指定副本数（选填）")
    allocatable_cpu_cores: float | None = Field(default=None, ge=1.0, description="自定义集群可分配 CPU 核心数")
    allocatable_memory_gib: float | None = Field(default=None, ge=1.0, description="自定义集群可分配内存 GiB")
    target_concurrency_per_worker: int | None = Field(default=None, ge=1, description="单 Worker 目标并发任务数")


class ApplyScalingIn(BaseModel):
    queue_depth: int = Field(..., ge=0, description="当前用例排队深度")
    force_replicas: int | None = Field(default=None, ge=1, description="强制指定目标副本（选填）")


@router.post("/evaluate")
async def evaluate_scaling_endpoint(
    body: EvaluateScalingIn,
    _user: User = Depends(get_current_user),
) -> dict[str, Any]:
    """评估任务队列排队状态并输出弹性扩缩容决策。"""
    _ = _user
    cfg = ClusterQuotaConfig()
    if body.allocatable_cpu_cores is not None:
        cfg.allocatable_cpu_cores = body.allocatable_cpu_cores
    if body.allocatable_memory_gib is not None:
        cfg.allocatable_memory_gib = body.allocatable_memory_gib
    if body.target_concurrency_per_worker is not None:
        cfg.target_concurrency_per_worker = body.target_concurrency_per_worker

    decision = evaluate_autoscaling(
        queue_depth=body.queue_depth,
        current_replicas=body.current_replicas,
        config=cfg,
    )
    return {"message": "弹性扩缩容决策评估完成", "decision": decision.to_dict()}


@router.post("/apply")
async def apply_scaling_endpoint(
    body: ApplyScalingIn,
    _user: User = Depends(require_engineer),
) -> dict[str, Any]:
    """执行并落地扩缩容决策（需工程师权限）。"""
    _ = _user
    decision = evaluate_autoscaling(queue_depth=body.queue_depth)
    if body.force_replicas is not None:
        decision.allocated_replicas = body.force_replicas
        decision.desired_replicas = body.force_replicas

    res = apply_autoscaling_decision(decision)
    return res


@router.get("/status")
async def get_cluster_status_endpoint(
    _user: User = Depends(get_current_user),
) -> dict[str, Any]:
    """查询当前集群活跃 Worker 状态与资源配额水位。"""
    _ = _user
    return get_current_cluster_status()


@router.get("/events")
async def list_scaling_events_endpoint(
    limit: int = 50,
    _user: User = Depends(get_current_user),
) -> dict[str, Any]:
    """获取扩缩容历史事件审计记录。"""
    _ = _user
    events = list_scaling_events(limit=limit)
    return {"total": len(events), "events": events}


@router.delete("/events")
async def clear_scaling_events_endpoint(
    _user: User = Depends(require_engineer),
) -> dict[str, Any]:
    """清空历史扩缩容事件（需工程师权限）。"""
    _ = _user
    clear_autoscaler_state()
    return {"message": "已重置弹性扩缩容事件与集群状态"}
