"""分布式海量虚拟用户发压调度与阶梯加压器服务 (T1.2)

构建企业级生产影子压测负载模型、阶梯加压计划与分布式发压节点资源精算:
1. 多样化负载模式定义 (STEP_RAMP_UP 阶梯爬坡, SPIKE_SURGE 瞬时脉冲, CONSTANT_STEADY 稳态, SOAK_LONGEVITY 耐久度);
2. 多阶段加压时间步进规划 (StressLoadPlan & StressStepStage: 虚拟用户数 VU 100~50,000);
3. 分布式发压集群 Worker 节点算力分配 (单 Pod 最大承载 2,000 VU，自动向上取整扩展 Worker 副本数与分片);
4. 压测阶段进阶自适应状态机 (evaluate_stress_step_progression: ADVANCE_NEXT_STAGE | MAINTAIN_CURRENT | COMPLETED)。
"""

from __future__ import annotations

import enum
import math
import uuid
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional


class StressLoadProfileType(str, enum.Enum):
    STEP_RAMP_UP = "STEP_RAMP_UP"  # 阶梯递进爬坡：每阶段平稳加压，挖掘拐点
    SPIKE_SURGE = "SPIKE_SURGE"  # 瞬时脉冲突刺：模拟大促整点高并发抢购
    CONSTANT_STEADY = "CONSTANT_STEADY"  # 恒定稳态并发：长时持续恒定负载测试
    SOAK_LONGEVITY = "SOAK_LONGEVITY"  # 长期浸泡耐久度：检验内存泄漏与连接池耗尽


class StressStepperAction(str, enum.Enum):
    ADVANCE_NEXT_STAGE = "ADVANCE_NEXT_STAGE"  # 当前阶段达标，推进至下一阶梯并发
    MAINTAIN_CURRENT = "MAINTAIN_CURRENT"  # 处于阶段观察期，保持当前发压强度
    COMPLETED_FULL_PLAN = "COMPLETED_FULL_PLAN"  # 全套阶梯发压计划顺利完成
    ABORT_OVERLOAD = "ABORT_OVERLOAD"  # 指标严重劣变，建议紧急泄压终止


# 单个分布式发压节点推荐承载的最大虚拟用户数 (Virtual Users)
MAX_VU_PER_WORKER_NODE = 2000


@dataclass
class StressStepStage:
    stage_index: int
    stage_name: str
    target_vu_count: int  # 目标虚拟并发用户数
    duration_seconds: int  # 本阶段持续时长 (秒)
    expected_tps_ceiling: float  # 预期吞吐量上限参考
    ramp_up_seconds: int = 10  # 爬坡达到目标并发所用时间

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class DistributedWorkerAllocation:
    plan_id: str
    target_peak_vu: int
    worker_nodes_count: int  # 所需发压节点数
    vu_per_worker: int  # 单节点分配的并发用户数
    total_assigned_vu: int
    memory_limit_mb_per_worker: int = 2048
    cpu_limit_cores_per_worker: float = 2.0

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class StressLoadPlan:
    plan_id: str
    plan_name: str
    target_service: str
    profile_type: StressLoadProfileType
    stages: List[StressStepStage]
    total_duration_seconds: int
    peak_vu_count: int
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S"))

    def to_dict(self) -> Dict[str, Any]:
        return {
            "plan_id": self.plan_id,
            "plan_name": self.plan_name,
            "target_service": self.target_service,
            "profile_type": self.profile_type.value,
            "stages": [s.to_dict() for s in self.stages],
            "total_duration_seconds": self.total_duration_seconds,
            "peak_vu_count": self.peak_vu_count,
            "created_at": self.created_at,
        }


@dataclass
class StressProgressionVerdict:
    verdict_id: str
    plan_id: str
    current_stage_index: int
    current_vu_count: int
    action: StressStepperAction
    recommended_next_vu: int
    message: str
    evaluated_at: str = field(default_factory=lambda: datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S"))

    def to_dict(self) -> Dict[str, Any]:
        return {
            "verdict_id": self.verdict_id,
            "plan_id": self.plan_id,
            "current_stage_index": self.current_stage_index,
            "current_vu_count": self.current_vu_count,
            "action": self.action.value,
            "recommended_next_vu": self.recommended_next_vu,
            "message": self.message,
            "evaluated_at": self.evaluated_at,
        }


def calculate_distributed_worker_allocation(
    target_peak_vu: int,
    plan_id: Optional[str] = None,
    max_vu_per_worker: int = MAX_VU_PER_WORKER_NODE,
) -> DistributedWorkerAllocation:
    """计算发压集群所需的分布式 Worker 节点副本数与资源分配"""
    peak_vu = max(1, target_peak_vu)
    workers_needed = max(1, math.ceil(peak_vu / max_vu_per_worker))
    vu_per_node = math.ceil(peak_vu / workers_needed)

    return DistributedWorkerAllocation(
        plan_id=plan_id or f"plan_{uuid.uuid4().hex[:8]}",
        target_peak_vu=peak_vu,
        worker_nodes_count=workers_needed,
        vu_per_worker=vu_per_node,
        total_assigned_vu=workers_needed * vu_per_node,
    )


def generate_standard_step_ramp_plan(
    target_service: str = "payment-service",
    initial_vu: int = 500,
    step_vu: int = 1000,
    steps_count: int = 5,
    stage_duration_seconds: int = 60,
) -> StressLoadPlan:
    """生成标准化阶梯加压计划 (Step Ramp-Up Plan)"""
    plan_id = f"plan_step_{uuid.uuid4().hex[:8]}"
    stages: List[StressStepStage] = []

    for i in range(steps_count):
        vu = initial_vu + i * step_vu
        stages.append(
            StressStepStage(
                stage_index=i + 1,
                stage_name=f"第 {i + 1} 阶梯加压 ({vu} VU)",
                target_vu_count=vu,
                duration_seconds=stage_duration_seconds,
                expected_tps_ceiling=float(vu * 15.0),
                ramp_up_seconds=10,
            )
        )

    peak_vu = stages[-1].target_vu_count if stages else initial_vu
    total_duration = sum(s.duration_seconds for s in stages)

    return StressLoadPlan(
        plan_id=plan_id,
        plan_name=f"[{target_service}] 标准五阶梯递进加压计划",
        target_service=target_service,
        profile_type=StressLoadProfileType.STEP_RAMP_UP,
        stages=stages,
        total_duration_seconds=total_duration,
        peak_vu_count=peak_vu,
    )


def evaluate_stress_step_progression(
    plan: StressLoadPlan,
    current_stage_index: int,
    stage_elapsed_seconds: int,
    current_error_rate_pct: float = 0.0,
    error_rate_threshold_pct: float = 1.0,
) -> StressProgressionVerdict:
    """自适应评估当前加压阶段状态并推演下一步调度动作"""
    verdict_id = f"st_ver_{uuid.uuid4().hex[:10]}"

    if not plan.stages:
        return StressProgressionVerdict(
            verdict_id=verdict_id,
            plan_id=plan.plan_id,
            current_stage_index=0,
            current_vu_count=0,
            action=StressStepperAction.COMPLETED_FULL_PLAN,
            recommended_next_vu=0,
            message="加压计划中无配置阶段",
        )

    # 1. 检查指标是否严重恶化触碰红线
    if current_error_rate_pct > error_rate_threshold_pct:
        return StressProgressionVerdict(
            verdict_id=verdict_id,
            plan_id=plan.plan_id,
            current_stage_index=current_stage_index,
            current_vu_count=plan.stages[min(current_stage_index - 1, len(plan.stages) - 1)].target_vu_count,
            action=StressStepperAction.ABORT_OVERLOAD,
            recommended_next_vu=0,
            message=f"错误率 {current_error_rate_pct:.2f}% 超过安全阈值 {error_rate_threshold_pct:.2f}%，触发过载保护！",
        )

    # 2. 获取当前阶段配置
    idx = max(1, min(current_stage_index, len(plan.stages)))
    curr_stage = plan.stages[idx - 1]

    # 3. 检查当前阶段时长是否满足
    if stage_elapsed_seconds < curr_stage.duration_seconds:
        remaining = curr_stage.duration_seconds - stage_elapsed_seconds
        return StressProgressionVerdict(
            verdict_id=verdict_id,
            plan_id=plan.plan_id,
            current_stage_index=curr_stage.stage_index,
            current_vu_count=curr_stage.target_vu_count,
            action=StressStepperAction.MAINTAIN_CURRENT,
            recommended_next_vu=curr_stage.target_vu_count,
            message=f"阶段 [{curr_stage.stage_name}] 正在稳态加压中，剩余 {remaining} 秒",
        )

    # 4. 当前阶段已满，若还有下一阶段，推进加压
    if idx < len(plan.stages):
        next_stage = plan.stages[idx]
        return StressProgressionVerdict(
            verdict_id=verdict_id,
            plan_id=plan.plan_id,
            current_stage_index=curr_stage.stage_index,
            current_vu_count=curr_stage.target_vu_count,
            action=StressStepperAction.ADVANCE_NEXT_STAGE,
            recommended_next_vu=next_stage.target_vu_count,
            message=f"阶段 [{curr_stage.stage_name}] 顺利达标，自适应晋级至 [{next_stage.stage_name}]",
        )

    # 5. 所有阶段全量完成
    return StressProgressionVerdict(
        verdict_id=verdict_id,
        plan_id=plan.plan_id,
        current_stage_index=curr_stage.stage_index,
        current_vu_count=curr_stage.target_vu_count,
        action=StressStepperAction.COMPLETED_FULL_PLAN,
        recommended_next_vu=curr_stage.target_vu_count,
        message="所有规划发压阶段已 100% 执行完成，系统平稳达标！",
    )
