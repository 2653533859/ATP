"""云原生弹性 HPA 自动扩缩容 API 路由 (D1.2)."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field

from app.api.deps import get_current_user, require_engineer
from app.models.user import User
from app.services.k8s_worker_provisioner import (
    list_worker_pods,
    provision_worker_pod,
    terminate_worker_pod,
)
from app.services.queue_backpressure_autoscaler import (
    HpaEvaluationDecision,
    HpaPolicyConfig,
    HpaScalingDirection,
    QueueBackpressureMetrics,
    evaluate_hpa_decision,
    get_hpa_policy,
    list_hpa_history,
    list_hpa_policies,
    mark_policy_scaled,
    register_hpa_policy,
)

router = APIRouter(prefix="/cloud-native/autoscaling", tags=["云原生弹性 HPA 自动扩缩容"])


class CreateHpaPolicyIn(BaseModel):
    policy_id: str = Field(min_length=2, max_length=64, description="HPA 策略标识")
    target_queue: str = Field(default="default", description="目标监控任务队列")
    min_replicas: int = Field(default=1, ge=1, le=100, description="最小保底 Pod 副本数")
    max_replicas: int = Field(default=20, ge=1, le=200, description="最大允许 Pod 副本数")
    target_concurrency_per_pod: int = Field(default=5, ge=1, description="单 Pod 期望承载并发度")
    target_latency_slo_sec: float = Field(default=15.0, ge=1.0, description="目标排队时延 SLO (秒)")
    scale_up_stabilization_sec: float = Field(default=0.0, ge=0.0, description="扩容平滑窗口 (秒)")
    scale_down_stabilization_sec: float = Field(default=60.0, ge=0.0, description="缩容冷却窗口 (秒)")
    enabled: bool = True


class EvaluateHpaIn(BaseModel):
    policy_id: str = Field(description="评估所用的 HPA 策略 ID")
    current_queue_depth: int = Field(ge=0, description="当前排队任务积压深度")
    running_tasks_count: int = Field(ge=0, description="正在执行任务数")
    p95_queue_latency_sec: float = Field(ge=0.0, description="当前 P95 排队时延 (秒)")
    current_replicas: int = Field(ge=0, description="当前运行的 Pod 副本数")


class ApplyHpaScalingIn(BaseModel):
    decision_id: str = Field(description="拟执行的 HPA 决策 ID")
    policy_id: str = Field(description="对应的 HPA 策略 ID")
    direction: str = Field(description="扩缩容方向: scale_up | scale_down | maintain")
    replicas_delta: int = Field(description="副本变更差值")
    target_queue: str = Field(default="default", description="目标队列")


@router.post("/policies")
async def create_hpa_policy_endpoint(
    body: CreateHpaPolicyIn,
    _user: User = Depends(require_engineer),
) -> dict[str, Any]:
    """创建或注册基于任务背压的 HPA 自动扩缩容策略 (需工程师权限)。"""
    _ = _user
    try:
        policy = HpaPolicyConfig(
            policy_id=body.policy_id,
            target_queue=body.target_queue,
            min_replicas=body.min_replicas,
            max_replicas=body.max_replicas,
            target_concurrency_per_pod=body.target_concurrency_per_pod,
            target_latency_slo_sec=body.target_latency_slo_sec,
            scale_up_stabilization_sec=body.scale_up_stabilization_sec,
            scale_down_stabilization_sec=body.scale_down_stabilization_sec,
            enabled=body.enabled,
        )
        register_hpa_policy(policy)
        return {"message": "HPA 策略注册成功", "policy": policy.to_dict()}
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))


@router.get("/policies")
async def list_hpa_policies_endpoint(
    _user: User = Depends(get_current_user),
) -> dict[str, Any]:
    """查询集群当前配置的所有 HPA 扩缩容策略列表。"""
    _ = _user
    policies = list_hpa_policies()
    return {"total": len(policies), "policies": [p.to_dict() for p in policies]}


@router.post("/evaluate")
async def evaluate_hpa_endpoint(
    body: EvaluateHpaIn,
    _user: User = Depends(get_current_user),
) -> dict[str, Any]:
    """结合当前队列积压与时延指标，执行自适应 HPA 扩缩容决策评估。"""
    _ = _user
    policy = get_hpa_policy(body.policy_id)
    if not policy:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"HPA 策略不存在: {body.policy_id}")

    metrics = QueueBackpressureMetrics(
        queue_name=policy.target_queue,
        current_queue_depth=body.current_queue_depth,
        running_tasks_count=body.running_tasks_count,
        p95_queue_latency_sec=body.p95_queue_latency_sec,
        current_replicas=body.current_replicas,
    )

    try:
        decision = evaluate_hpa_decision(body.policy_id, metrics)
        return decision.to_dict()
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))


@router.post("/apply")
async def apply_hpa_scaling_endpoint(
    body: ApplyHpaScalingIn,
    _user: User = Depends(require_engineer),
) -> dict[str, Any]:
    """执行 HPA 决策结果：自动联动 K8s / Docker 实例拉起或销毁。"""
    _ = _user
    policy = get_hpa_policy(body.policy_id)
    if not policy:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"HPA 策略不存在: {body.policy_id}")

    action_details: list[str] = []
    if body.direction == HpaScalingDirection.SCALE_UP.value and body.replicas_delta > 0:
        for i in range(body.replicas_delta):
            pod = provision_worker_pod(
                worker_name=f"hpa-worker-{body.target_queue}-{i+1}",
                assigned_queue=body.target_queue,
            )
            action_details.append(f"Provisioned pod: {pod.pod_id}")
        mark_policy_scaled(body.policy_id)
    elif body.direction == HpaScalingDirection.SCALE_DOWN.value and body.replicas_delta < 0:
        # 获取当前运行在该队列的 Pod 实例执行终止
        pods = [p for p in list_worker_pods(assigned_queue=body.target_queue) if p.status.value == "running"]
        terminate_count = min(abs(body.replicas_delta), len(pods))
        for p in pods[:terminate_count]:
            terminate_worker_pod(p.pod_id, exit_code=0)
            action_details.append(f"Terminated pod: {p.pod_id}")
        mark_policy_scaled(body.policy_id)

    return {
        "message": "HPA 扩缩容联动执行完成",
        "policy_id": body.policy_id,
        "direction": body.direction,
        "replicas_delta": body.replicas_delta,
        "executed_actions": action_details,
    }


@router.get("/history")
async def list_hpa_history_endpoint(
    policy_id: str | None = Query(default=None, description="按策略 ID 筛选"),
    _user: User = Depends(get_current_user),
) -> dict[str, Any]:
    """获取 HPA 自动扩缩容历史决策记录与指标快照。"""
    _ = _user
    history: list[HpaEvaluationDecision] = list_hpa_history(policy_id=policy_id)
    return {"total": len(history), "history": [d.to_dict() for d in history]}
