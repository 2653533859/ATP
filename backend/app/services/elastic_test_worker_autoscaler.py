"""云原生动态 Worker 容器 Pod 弹性扩缩容与集群资源配额仲裁器 (T1.1)。"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any


class ScalingAction(str, Enum):
    """弹性扩缩容动作分类。"""

    SCALE_UP = "SCALE_UP"
    SCALE_DOWN = "SCALE_DOWN"
    NOOP = "NOOP"
    QUOTA_BLOCKED = "QUOTA_BLOCKED"


class QuotaArbitrationStatus(str, Enum):
    """集群资源配额仲裁状态。"""

    SUFFICIENT = "SUFFICIENT"
    ARBITRATED_DEGRADED = "ARBITRATED_DEGRADED"
    EXHAUSTED = "EXHAUSTED"


@dataclass
class ClusterQuotaConfig:
    """集群资源配额与限制参数。"""

    allocatable_cpu_cores: float = 32.0
    allocatable_memory_gib: float = 64.0
    worker_request_cpu: float = 0.5
    worker_request_memory_gib: float = 1.0
    min_replicas: int = 1
    max_replicas: int = 20
    target_concurrency_per_worker: int = 4
    scale_up_cooldown_seconds: int = 30
    scale_down_cooldown_seconds: int = 120


@dataclass
class ScalingDecision:
    """扩缩容裁决结果。"""

    decision_id: str
    action: ScalingAction
    current_replicas: int
    desired_replicas: int
    allocated_replicas: int
    queue_depth: int
    reason: str
    arbitration_status: QuotaArbitrationStatus
    cpu_utilization_estimate_pct: float
    memory_utilization_estimate_pct: float
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def to_dict(self) -> dict[str, Any]:
        return {
            "decision_id": self.decision_id,
            "action": self.action.value,
            "current_replicas": self.current_replicas,
            "desired_replicas": self.desired_replicas,
            "allocated_replicas": self.allocated_replicas,
            "queue_depth": self.queue_depth,
            "reason": self.reason,
            "arbitration_status": self.arbitration_status.value,
            "cpu_utilization_estimate_pct": round(self.cpu_utilization_estimate_pct, 1),
            "memory_utilization_estimate_pct": round(self.memory_utilization_estimate_pct, 1),
            "created_at": self.created_at.isoformat(),
        }


# 全局状态存储
_SCALING_EVENTS: list[ScalingDecision] = []
_CURRENT_ACTIVE_REPLICAS: int = 2
_LAST_SCALE_TIME: datetime | None = None


def clear_autoscaler_state() -> None:
    """重置弹性扩缩容状态（单测专用）。"""
    global _SCALING_EVENTS, _CURRENT_ACTIVE_REPLICAS, _LAST_SCALE_TIME
    _SCALING_EVENTS = []
    _CURRENT_ACTIVE_REPLICAS = 2
    _LAST_SCALE_TIME = None


def get_current_cluster_status() -> dict[str, Any]:
    """获取当前集群状态与配额使用率。"""
    cfg = ClusterQuotaConfig()
    used_cpu = _CURRENT_ACTIVE_REPLICAS * cfg.worker_request_cpu
    used_mem = _CURRENT_ACTIVE_REPLICAS * cfg.worker_request_memory_gib
    return {
        "current_active_replicas": _CURRENT_ACTIVE_REPLICAS,
        "min_replicas": cfg.min_replicas,
        "max_replicas": cfg.max_replicas,
        "allocatable_cpu_cores": cfg.allocatable_cpu_cores,
        "allocatable_memory_gib": cfg.allocatable_memory_gib,
        "used_cpu_cores": round(used_cpu, 2),
        "used_memory_gib": round(used_mem, 2),
        "cpu_usage_pct": round((used_cpu / cfg.allocatable_cpu_cores) * 100, 1),
        "memory_usage_pct": round((used_mem / cfg.allocatable_memory_gib) * 100, 1),
        "last_scale_time": _LAST_SCALE_TIME.isoformat() if _LAST_SCALE_TIME else None,
        "total_scaling_events": len(_SCALING_EVENTS),
    }


def evaluate_autoscaling(
    queue_depth: int,
    current_replicas: int | None = None,
    config: ClusterQuotaConfig | None = None,
) -> ScalingDecision:
    """评估当前负载与排队深度，推导弹性扩缩容决策。"""
    cfg = config or ClusterQuotaConfig()
    cur = _CURRENT_ACTIVE_REPLICAS if current_replicas is None else current_replicas

    # 1. 计算理论期望副本数
    if queue_depth <= 0:
        desired = cfg.min_replicas
    else:
        desired = math.ceil(queue_depth / cfg.target_concurrency_per_worker)
        desired = max(cfg.min_replicas, min(cfg.max_replicas, desired))

    # 2. 计算集群物理资源所能支撑的最大 Pod 数量
    max_pods_by_cpu = int(cfg.allocatable_cpu_cores // cfg.worker_request_cpu)
    max_pods_by_mem = int(cfg.allocatable_memory_gib // cfg.worker_request_memory_gib)
    hardware_capacity = min(max_pods_by_cpu, max_pods_by_mem, cfg.max_replicas)

    action = ScalingAction.NOOP
    allocated = cur
    arbitration = QuotaArbitrationStatus.SUFFICIENT
    reason = "当前 Worker 节点数与任务排队深度均衡，无需扩缩容。"

    if desired > cur:
        if cur >= hardware_capacity:
            action = ScalingAction.QUOTA_BLOCKED
            allocated = cur
            arbitration = QuotaArbitrationStatus.EXHAUSTED
            reason = f"队列积压({queue_depth})期望扩容至 {desired} 副本，但已触及集群物理硬件配额上限 ({hardware_capacity})，禁止超额扩容。"
        elif desired > hardware_capacity:
            action = ScalingAction.SCALE_UP
            allocated = hardware_capacity
            arbitration = QuotaArbitrationStatus.ARBITRATED_DEGRADED
            reason = f"期望扩容至 {desired} 副本，经集群资源配额仲裁，降级扩容至最大可用容量 {hardware_capacity} 副本。"
        else:
            action = ScalingAction.SCALE_UP
            allocated = desired
            arbitration = QuotaArbitrationStatus.SUFFICIENT
            reason = f"检测到任务队列积压({queue_depth})，动态扩容 Worker 副本：{cur} -> {desired}。"
    elif desired < cur:
        action = ScalingAction.SCALE_DOWN
        allocated = desired
        arbitration = QuotaArbitrationStatus.SUFFICIENT
        reason = f"任务队列空闲({queue_depth})，平滑缩容释放空闲云资源：{cur} -> {desired}。"

    cpu_est = (allocated * cfg.worker_request_cpu / cfg.allocatable_cpu_cores) * 100.0
    mem_est = (allocated * cfg.worker_request_memory_gib / cfg.allocatable_memory_gib) * 100.0

    now = datetime.now(timezone.utc)
    decision = ScalingDecision(
        decision_id=f"scale_{int(now.timestamp())}_{queue_depth}",
        action=action,
        current_replicas=cur,
        desired_replicas=desired,
        allocated_replicas=allocated,
        queue_depth=queue_depth,
        reason=reason,
        arbitration_status=arbitration,
        cpu_utilization_estimate_pct=cpu_est,
        memory_utilization_estimate_pct=mem_est,
        created_at=now,
    )
    return decision


def apply_autoscaling_decision(decision: ScalingDecision) -> dict[str, Any]:
    """执行并落地扩缩容决策，更新集群活跃 Worker 副本。"""
    global _CURRENT_ACTIVE_REPLICAS, _LAST_SCALE_TIME
    if decision.action in (ScalingAction.SCALE_UP, ScalingAction.SCALE_DOWN):
        _CURRENT_ACTIVE_REPLICAS = decision.allocated_replicas
        _LAST_SCALE_TIME = datetime.now(timezone.utc)

    _SCALING_EVENTS.append(decision)
    return {
        "status": "APPLIED" if decision.action != ScalingAction.QUOTA_BLOCKED else "BLOCKED",
        "decision": decision.to_dict(),
        "active_replicas": _CURRENT_ACTIVE_REPLICAS,
        "message": f"扩缩容动作 [{decision.action.value}] 已执行，当前集群活跃 Worker 副本为 {_CURRENT_ACTIVE_REPLICAS}。",
    }


def list_scaling_events(limit: int = 50) -> list[dict[str, Any]]:
    """获取扩缩容历史事件审计记录。"""
    events = list(reversed(_SCALING_EVENTS))
    return [e.to_dict() for e in events[:limit]]
