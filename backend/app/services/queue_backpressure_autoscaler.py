"""基于任务背压与队列等待时延的弹性 HPA 自动扩缩容算法 (D1.2).

采集各任务队列实时积压深度（Queue Depth）与历史 P95 排队时延（Queue Latency），
结合 Pod 单实例并发承载力与时延 SLO，自适应计算目标副本数并执行防震荡扩缩容决策。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
import math
from typing import Any
import uuid

import logging

logger = logging.getLogger(__name__)


class HpaScalingDirection(str, Enum):
    SCALE_UP = "scale_up"
    SCALE_DOWN = "scale_down"
    MAINTAIN = "maintain"


@dataclass
class HpaPolicyConfig:
    policy_id: str
    target_queue: str = "default"
    min_replicas: int = 1
    max_replicas: int = 20
    target_concurrency_per_pod: int = 5
    target_latency_slo_sec: float = 15.0
    scale_up_stabilization_sec: float = 0.0
    scale_down_stabilization_sec: float = 60.0
    enabled: bool = True

    def validate(self) -> None:
        if self.min_replicas < 1:
            raise ValueError("min_replicas 至少为 1")
        if self.max_replicas < self.min_replicas:
            raise ValueError("max_replicas 不能小于 min_replicas")
        if self.target_concurrency_per_pod <= 0:
            raise ValueError("target_concurrency_per_pod 必须大于 0")
        if self.target_latency_slo_sec <= 0:
            raise ValueError("target_latency_slo_sec 必须大于 0")

    def to_dict(self) -> dict[str, Any]:
        return {
            "policy_id": self.policy_id,
            "target_queue": self.target_queue,
            "min_replicas": self.min_replicas,
            "max_replicas": self.max_replicas,
            "target_concurrency_per_pod": self.target_concurrency_per_pod,
            "target_latency_slo_sec": self.target_latency_slo_sec,
            "scale_up_stabilization_sec": self.scale_up_stabilization_sec,
            "scale_down_stabilization_sec": self.scale_down_stabilization_sec,
            "enabled": self.enabled,
        }


@dataclass
class QueueBackpressureMetrics:
    queue_name: str
    current_queue_depth: int
    running_tasks_count: int
    p95_queue_latency_sec: float
    current_replicas: int

    def to_dict(self) -> dict[str, Any]:
        return {
            "queue_name": self.queue_name,
            "current_queue_depth": self.current_queue_depth,
            "running_tasks_count": self.running_tasks_count,
            "p95_queue_latency_sec": self.p95_queue_latency_sec,
            "current_replicas": self.current_replicas,
        }


@dataclass
class HpaEvaluationDecision:
    decision_id: str
    policy_id: str
    target_queue: str
    direction: HpaScalingDirection
    current_replicas: int
    desired_replicas: int
    replicas_delta: int
    reason: str
    evaluated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    metrics_snapshot: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "decision_id": self.decision_id,
            "policy_id": self.policy_id,
            "target_queue": self.target_queue,
            "direction": self.direction.value,
            "current_replicas": self.current_replicas,
            "desired_replicas": self.desired_replicas,
            "replicas_delta": self.replicas_delta,
            "reason": self.reason,
            "evaluated_at": self.evaluated_at.isoformat(),
            "metrics_snapshot": self.metrics_snapshot,
        }


# 内存策略库与审计决策历史
_HPA_POLICIES: dict[str, HpaPolicyConfig] = {}
_LAST_SCALED_AT: dict[str, datetime] = {}
_HPA_DECISION_HISTORY: list[HpaEvaluationDecision] = []


def register_hpa_policy(policy: HpaPolicyConfig) -> None:
    """注册或更新 HPA 自动扩缩容策略。"""
    policy.validate()
    _HPA_POLICIES[policy.policy_id] = policy
    logger.info("Registered HPA policy policy_id=%s queue=%s", policy.policy_id, policy.target_queue)


def get_hpa_policy(policy_id: str) -> HpaPolicyConfig | None:
    """获取指定 HPA 策略配置。"""
    return _HPA_POLICIES.get(policy_id)


def list_hpa_policies() -> list[HpaPolicyConfig]:
    """获取所有 HPA 策略列表。"""
    return list(_HPA_POLICIES.values())


def evaluate_hpa_decision(
    policy_id: str,
    metrics: QueueBackpressureMetrics,
    now: datetime | None = None,
) -> HpaEvaluationDecision:
    """核心决策算法：结合队列背压深度与 P95 时延测算目标副本数。"""
    policy = _HPA_POLICIES.get(policy_id)
    if not policy:
        raise ValueError(f"HPA 策略不存在: {policy_id}")

    if not policy.enabled:
        return HpaEvaluationDecision(
            decision_id=f"hpa_dec_{uuid.uuid4().hex[:12]}",
            policy_id=policy_id,
            target_queue=metrics.queue_name,
            direction=HpaScalingDirection.MAINTAIN,
            current_replicas=metrics.current_replicas,
            desired_replicas=metrics.current_replicas,
            replicas_delta=0,
            reason="HPA 策略已被禁用",
            metrics_snapshot=metrics.to_dict(),
        )

    current_time = now or datetime.now(timezone.utc)
    total_load = metrics.current_queue_depth + metrics.running_tasks_count

    if total_load == 0:
        raw_desired = policy.min_replicas
        reason = f"队列空闲无积压，缩容至最小保底副本数 {policy.min_replicas}"
    else:
        # 1. 基础承载副本需求
        base_needed = total_load / float(policy.target_concurrency_per_pod)
        # 2. 时延违约惩罚因子 (当 P95 时延超出 SLO 时额外激进扩容)
        latency_penalty = max(0.0, (metrics.p95_queue_latency_sec / float(policy.target_latency_slo_sec)) - 1.0)
        # 3. 目标期望副本计算 (带向上取整)
        raw_desired = math.ceil(base_needed * (1.0 + 0.5 * latency_penalty))
        reason = (
            f"负载积压 {total_load} 个任务 (基准需 {base_needed:.1f} Pod)，"
            f"P95时延 {metrics.p95_queue_latency_sec:.1f}s (SLO: {policy.target_latency_slo_sec:.1f}s, 惩罚因子 {latency_penalty:.2f})"
        )

    # 4. 边界硬性夹紧 (Clamp min ~ max)
    desired_replicas = max(policy.min_replicas, min(policy.max_replicas, raw_desired))
    delta = desired_replicas - metrics.current_replicas

    direction = HpaScalingDirection.MAINTAIN
    if delta > 0:
        direction = HpaScalingDirection.SCALE_UP
    elif delta < 0:
        # 5. 缩容冷却防震荡窗口检测
        last_scaled = _LAST_SCALED_AT.get(policy_id)
        if last_scaled:
            cooldown_passed = (current_time - last_scaled).total_seconds()
            if cooldown_passed < policy.scale_down_stabilization_sec:
                direction = HpaScalingDirection.MAINTAIN
                desired_replicas = metrics.current_replicas
                delta = 0
                reason += f"；由于处于缩容冷却窗口内 ({cooldown_passed:.1f}s < {policy.scale_down_stabilization_sec:.1f}s)，抑制缩容"
            else:
                direction = HpaScalingDirection.SCALE_DOWN
        else:
            direction = HpaScalingDirection.SCALE_DOWN

    decision = HpaEvaluationDecision(
        decision_id=f"hpa_dec_{uuid.uuid4().hex[:12]}",
        policy_id=policy_id,
        target_queue=metrics.queue_name,
        direction=direction,
        current_replicas=metrics.current_replicas,
        desired_replicas=desired_replicas,
        replicas_delta=delta,
        reason=reason,
        evaluated_at=current_time,
        metrics_snapshot=metrics.to_dict(),
    )

    _HPA_DECISION_HISTORY.append(decision)
    logger.info(
        "HPA decision calculated policy_id=%s direction=%s current=%s desired=%s delta=%s",
        policy_id,
        direction.value,
        metrics.current_replicas,
        desired_replicas,
        delta,
    )
    return decision


def mark_policy_scaled(policy_id: str, scaled_at: datetime | None = None) -> None:
    """更新策略最近扩缩容时间戳。"""
    _LAST_SCALED_AT[policy_id] = scaled_at or datetime.now(timezone.utc)


def list_hpa_history(policy_id: str | None = None) -> list[HpaEvaluationDecision]:
    """查询 HPA 扩缩容评估历史记录。"""
    if policy_id:
        return [d for d in _HPA_DECISION_HISTORY if d.policy_id == policy_id]
    return list(_HPA_DECISION_HISTORY)


def reset_hpa_registry() -> None:
    """供单元测试清理状态使用。"""
    _HPA_POLICIES.clear()
    _LAST_SCALED_AT.clear()
    _HPA_DECISION_HISTORY.clear()
