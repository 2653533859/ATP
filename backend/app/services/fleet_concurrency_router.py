"""物理真机动态多目标加权并发路由引擎服务 (T1.2)

为多端自动化任务与 AI 自主探索提供物理设备全局最优派发与配额租约管理:
1. 任务需求规格建模 (TaskExecutionRequirement: 平台偏好、电量阈值、最高温度门限、优先级);
2. 多目标加权适应度打分算法 (Best-Fit Multi-Objective Fitness Scoring);
3. 动态并发配额租约与释放机制 (Device Concurrency Lease & Release);
4. 路由决策过程结构化追踪与审计。
"""

from __future__ import annotations

import enum
import uuid
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Set

from app.services.fleet_health_telemetry import (
    DeviceHealthMetric,
    get_device_telemetry,
    is_device_eligible_for_dispatch,
    list_fleet_telemetry,
)


class TaskPriority(str, enum.Enum):
    CRITICAL = "CRITICAL"  # P0 级阻塞型核心任务
    HIGH = "HIGH"  # P1 级高优先级用例
    NORMAL = "NORMAL"  # P2 级普通回归
    LOW = "LOW"  # P3 级长尾压测/巡检


class RoutingStatus(str, enum.Enum):
    ROUTED = "ROUTED"  # 成功路由并锁定设备配额
    QUEUED = "QUEUED"  # 设备暂满，进入缓冲队列
    NO_AVAILABLE_DEVICE = "NO_AVAILABLE_DEVICE"  # 无可用健康设备 (如全过热/全离线)


@dataclass
class TaskExecutionRequirement:
    task_id: str
    target_platform: str  # ios | android
    task_name: str = "移动端自动化执行任务"
    preferred_device_id: Optional[str] = None
    min_battery_percent: int = 20
    max_temperature_c: float = 42.0
    priority: TaskPriority = TaskPriority.NORMAL
    estimated_duration_sec: int = 60

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        d["priority"] = self.priority.value
        return d


@dataclass
class CandidateDeviceEvaluation:
    device_id: str
    platform: str
    eligible: bool
    disqualify_reason: str = ""
    health_score: float = 0.0
    load_margin_score: float = 0.0
    latency_score: float = 0.0
    affinity_score: float = 0.0
    composite_fitness: float = 0.0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "device_id": self.device_id,
            "platform": self.platform,
            "eligible": self.eligible,
            "disqualify_reason": self.disqualify_reason,
            "health_score": round(self.health_score, 2),
            "load_margin_score": round(self.load_margin_score, 2),
            "latency_score": round(self.latency_score, 2),
            "affinity_score": round(self.affinity_score, 2),
            "composite_fitness": round(self.composite_fitness, 2),
        }


@dataclass
class RoutingDecisionResult:
    decision_id: str
    task_id: str
    target_platform: str
    status: RoutingStatus
    selected_device_id: Optional[str]
    fitness_score: float
    candidate_evaluations: List[CandidateDeviceEvaluation]
    routing_reason: str
    allocated_at: str = field(default_factory=lambda: datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S"))

    def to_dict(self) -> Dict[str, Any]:
        return {
            "decision_id": self.decision_id,
            "task_id": self.task_id,
            "target_platform": self.target_platform,
            "status": self.status.value,
            "selected_device_id": self.selected_device_id,
            "fitness_score": round(self.fitness_score, 2),
            "candidate_evaluations": [c.to_dict() for c in self.candidate_evaluations],
            "routing_reason": self.routing_reason,
            "allocated_at": self.allocated_at,
        }


_ROUTING_HISTORY: Dict[str, RoutingDecisionResult] = {}
_ACTIVE_LEASES: Dict[str, Set[str]] = {}  # device_id -> set of task_ids


def clear_routing_state() -> None:
    """清空路由历史与租约（测试夹具使用）"""
    _ROUTING_HISTORY.clear()
    _ACTIVE_LEASES.clear()


def evaluate_device_fitness(
    device: DeviceHealthMetric,
    requirement: TaskExecutionRequirement,
) -> CandidateDeviceEvaluation:
    """计算单台设备对于任务的多目标适应度得分"""
    # 1. 资格准入审查
    is_eligible, reason = is_device_eligible_for_dispatch(device.device_id)
    if not is_eligible:
        return CandidateDeviceEvaluation(
            device_id=device.device_id,
            platform=device.platform,
            eligible=False,
            disqualify_reason=reason,
        )

    # 检查电池阈值与温度阈值
    if device.battery_temperature_c > requirement.max_temperature_c:
        return CandidateDeviceEvaluation(
            device_id=device.device_id,
            platform=device.platform,
            eligible=False,
            disqualify_reason=f"温度 ({device.battery_temperature_c}°C) 超出任务允许门限 ({requirement.max_temperature_c}°C)",
        )

    if device.battery_level_percent < requirement.min_battery_percent:
        return CandidateDeviceEvaluation(
            device_id=device.device_id,
            platform=device.platform,
            eligible=False,
            disqualify_reason=f"电量 ({device.battery_level_percent}%) 低于任务最低要求 ({requirement.min_battery_percent}%)",
        )

    # 2. 四维适应度得分计算
    # 健康度 (40%)
    health_score = device.health_score

    # 负载余量 (30%)
    if device.max_concurrency > 0:
        load_margin = (1.0 - (device.current_concurrency / device.max_concurrency)) * 100.0
    else:
        load_margin = 0.0

    # 时延优势 (20%): RTT <= 20ms 得 100 分，>120ms 降至 20 分
    if device.tunnel_rtt_ms <= 20.0:
        latency_score = 100.0
    elif device.tunnel_rtt_ms <= 60.0:
        latency_score = 80.0
    elif device.tunnel_rtt_ms <= 120.0:
        latency_score = 50.0
    else:
        latency_score = 20.0

    # 亲和度奖励 (10%)
    affinity_score = 100.0 if requirement.preferred_device_id == device.device_id else 50.0

    # 综合适应度汇总
    composite = health_score * 0.40 + load_margin * 0.30 + latency_score * 0.20 + affinity_score * 0.10

    return CandidateDeviceEvaluation(
        device_id=device.device_id,
        platform=device.platform,
        eligible=True,
        disqualify_reason="",
        health_score=health_score,
        load_margin_score=load_margin,
        latency_score=latency_score,
        affinity_score=affinity_score,
        composite_fitness=composite,
    )


def route_and_lease_device(requirement: TaskExecutionRequirement) -> RoutingDecisionResult:
    """在设备集群中自适应挑选最优真机并锁定执行配额租约"""
    decision_id = f"route_{uuid.uuid4().hex[:12]}"

    # 获取同平台候选设备集合
    candidates = list_fleet_telemetry(platform=requirement.target_platform)
    evaluations: List[CandidateDeviceEvaluation] = []

    for dev in candidates:
        eval_res = evaluate_device_fitness(dev, requirement)
        evaluations.append(eval_res)

    eligible_cands = [e for e in evaluations if e.eligible]

    if not eligible_cands:
        # 无可用设备
        if not candidates:
            reason = f"集群中未注册任何 [{requirement.target_platform}] 平台的物理真机"
            status = RoutingStatus.NO_AVAILABLE_DEVICE
        else:
            reason = (
                f"集群中 {len(candidates)} 台 [{requirement.target_platform}] 设备均因过热、低电量或满载未通过准入门禁"
            )
            status = RoutingStatus.QUEUED

        decision = RoutingDecisionResult(
            decision_id=decision_id,
            task_id=requirement.task_id,
            target_platform=requirement.target_platform,
            status=status,
            selected_device_id=None,
            fitness_score=0.0,
            candidate_evaluations=evaluations,
            routing_reason=reason,
        )
        _ROUTING_HISTORY[decision_id] = decision
        return decision

    # 按综合适应度由高到低排序，选出最优设备
    eligible_cands.sort(key=lambda x: x.composite_fitness, reverse=True)
    best_candidate = eligible_cands[0]
    chosen_device_id = best_candidate.device_id

    # 锁定设备并发租约
    chosen_device = get_device_telemetry(chosen_device_id)
    if chosen_device:
        chosen_device.current_concurrency += 1
        if chosen_device_id not in _ACTIVE_LEASES:
            _ACTIVE_LEASES[chosen_device_id] = set()
        _ACTIVE_LEASES[chosen_device_id].add(requirement.task_id)

    decision = RoutingDecisionResult(
        decision_id=decision_id,
        task_id=requirement.task_id,
        target_platform=requirement.target_platform,
        status=RoutingStatus.ROUTED,
        selected_device_id=chosen_device_id,
        fitness_score=best_candidate.composite_fitness,
        candidate_evaluations=evaluations,
        routing_reason=f"全局最优匹配: 综合适应度得分 {round(best_candidate.composite_fitness, 1)} 分，当前并发水位占用 +1",
    )
    _ROUTING_HISTORY[decision_id] = decision
    return decision


def release_device_lease(device_id: str, task_id: str) -> bool:
    """释放真机任务执行租约并扣减并发计数"""
    dev = get_device_telemetry(device_id)
    if dev:
        dev.current_concurrency = max(0, dev.current_concurrency - 1)

    if device_id in _ACTIVE_LEASES and task_id in _ACTIVE_LEASES[device_id]:
        _ACTIVE_LEASES[device_id].remove(task_id)
        return True
    return False


def get_routing_decision(decision_id: str) -> Optional[RoutingDecisionResult]:
    """查询单次调度决策记录"""
    return _ROUTING_HISTORY.get(decision_id)


def list_routing_history(limit: int = 50) -> List[Dict[str, Any]]:
    """获取近期调度决策流水列表"""
    items = list(_ROUTING_HISTORY.values())
    items.sort(key=lambda x: x.allocated_at, reverse=True)
    return [i.to_dict() for i in items[:limit]]
