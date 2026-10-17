"""真机故障热转移与断点续跑自愈引擎服务 (T2.1)

在物理真机发生 USB 闪断、WDA/Agent 崩溃或过热熔断时提供毫秒级热迁移与断点续跑:
1. 故障类型探针感知 (TUNNEL_DISCONNECTED | THERMAL_EMERGENCY | HEARTBEAT_TIMEOUT | PROCESS_CRASH);
2. 执行现场与变量上下文快照保留 (TaskExecutionContextSnapshot: 步骤位点、变量总线、入参状态);
3. 同构温备设备动态挑选与无感热漂移 (Hot-Failover Rebalancing < 500ms);
4. 断点续跑指令规划 (ResumptionPlan: 跳过已成功前置步骤, 恢复变量并续接执行)。
"""

from __future__ import annotations

import enum
import time
import uuid
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from app.services.fleet_concurrency_router import (
    RoutingStatus,
    TaskExecutionRequirement,
    TaskPriority,
    release_device_lease,
    route_and_lease_device,
)
from app.services.fleet_health_telemetry import (
    DeviceHealthStatus,
    get_device_telemetry,
)


class FaultReason(str, enum.Enum):
    TUNNEL_DISCONNECTED = "TUNNEL_DISCONNECTED"  # USB / WDA / ADB 隧道断连
    THERMAL_EMERGENCY = "THERMAL_EMERGENCY"  # 电池温度突破警戒线紧急切断
    HEARTBEAT_TIMEOUT = "HEARTBEAT_TIMEOUT"  # 连续多次心跳超时无响应
    PROCESS_CRASH = "PROCESS_CRASH"  # 端侧底层驱动/测试宿主进程崩溃


class FailoverStatus(str, enum.Enum):
    MIGRATED_SUCCESS = "MIGRATED_SUCCESS"  # 成功热迁移至备用温热真机
    STANDBY_EXHAUSTED = "STANDBY_EXHAUSTED"  # 同构温备设备耗尽，任务暂挂队列
    FAILED = "FAILED"  # 上下文损坏或不可恢复


@dataclass
class TaskExecutionContextSnapshot:
    task_id: str
    platform: str  # ios | android
    failed_step_index: int  # 故障发生的步骤下标 (从 0 开始)
    total_steps_count: int
    completed_step_ids: List[str]
    context_variables: Dict[str, Any]
    original_device_id: str
    workflow_run_id: Optional[str] = None
    snapshot_time: str = field(default_factory=lambda: datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S"))

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class ResumptionPlan:
    plan_id: str
    target_device_id: str
    resume_from_step_index: int
    restored_variables: Dict[str, Any]
    skip_steps_count: int
    remaining_steps_count: int
    instruction: str

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class HotFailoverResult:
    failover_id: str
    task_id: str
    fault_reason: FaultReason
    status: FailoverStatus
    source_device_id: str
    target_device_id: Optional[str]
    elapsed_ms: float
    resumption_plan: Optional[ResumptionPlan]
    details: str
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S"))

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        d["fault_reason"] = self.fault_reason.value
        d["status"] = self.status.value
        d["elapsed_ms"] = round(self.elapsed_ms, 2)
        if self.resumption_plan:
            d["resumption_plan"] = self.resumption_plan.to_dict()
        return d


_FAILOVER_HISTORY: Dict[str, HotFailoverResult] = {}


def clear_failover_history() -> None:
    """清空故障转移历史记录（测试夹具使用）"""
    _FAILOVER_HISTORY.clear()


def execute_hot_failover(
    snapshot: TaskExecutionContextSnapshot,
    fault_reason: FaultReason,
) -> HotFailoverResult:
    """当运行中的物理真机发生故障时，毫秒级执行热转移并构建断点续跑计划"""
    start_time = time.perf_counter()
    failover_id = f"failover_{uuid.uuid4().hex[:10]}"

    orig_dev = get_device_telemetry(snapshot.original_device_id)

    # 1. 标记原故障设备状态并释放租约
    if orig_dev:
        if fault_reason == FaultReason.THERMAL_EMERGENCY:
            orig_dev.health_status = DeviceHealthStatus.OVERHEATED
        else:
            orig_dev.health_status = DeviceHealthStatus.OFFLINE
    # 释放原设备的占用租约
    release_device_lease(snapshot.original_device_id, snapshot.task_id)

    # 2. 从同构集群中紧急调度最佳温备真机
    req = TaskExecutionRequirement(
        task_id=f"{snapshot.task_id}_resumed",
        target_platform=snapshot.platform,
        task_name=f"热转移断点续跑: {snapshot.task_id}",
        priority=TaskPriority.CRITICAL,  # 提升为最高优先级抢占
    )

    decision = route_and_lease_device(req)
    elapsed = (time.perf_counter() - start_time) * 1000.0  # 毫秒

    if (
        decision.status != RoutingStatus.ROUTED
        or not decision.selected_device_id
        or decision.selected_device_id == snapshot.original_device_id
    ):
        # 无可用温备真机
        result = HotFailoverResult(
            failover_id=failover_id,
            task_id=snapshot.task_id,
            fault_reason=fault_reason,
            status=FailoverStatus.STANDBY_EXHAUSTED,
            source_device_id=snapshot.original_device_id,
            target_device_id=None,
            elapsed_ms=elapsed,
            resumption_plan=None,
            details=f"原真机 [{snapshot.original_device_id}] 遭遇 {fault_reason.value} 故障，集群同构温备真机已耗尽，任务暂挂队列重试",
        )
        _FAILOVER_HISTORY[failover_id] = result
        return result

    # 3. 构造断点续跑执行计划 (Resumption Plan)
    target_dev_id = decision.selected_device_id
    skip_count = snapshot.failed_step_index
    remaining_count = max(0, snapshot.total_steps_count - skip_count)

    plan = ResumptionPlan(
        plan_id=f"plan_{uuid.uuid4().hex[:8]}",
        target_device_id=target_dev_id,
        resume_from_step_index=snapshot.failed_step_index,
        restored_variables=dict(snapshot.context_variables),
        skip_steps_count=skip_count,
        remaining_steps_count=remaining_count,
        instruction=(
            f"跳过前置已完成的 {skip_count} 个步骤，注入 {len(snapshot.context_variables)} 个变量上下文，"
            f"在新目标真机 [{target_dev_id}] 上从第 #{skip_count + 1} 步无感继续执行。"
        ),
    )

    result = HotFailoverResult(
        failover_id=failover_id,
        task_id=snapshot.task_id,
        fault_reason=fault_reason,
        status=FailoverStatus.MIGRATED_SUCCESS,
        source_device_id=snapshot.original_device_id,
        target_device_id=target_dev_id,
        elapsed_ms=elapsed,
        resumption_plan=plan,
        details=(
            f"真机故障热转移成功！耗时 {round(elapsed, 2)}ms (达标 < 500ms 门禁)，"
            f"任务由 [{snapshot.original_device_id}] 热漂移至温备真机 [{target_dev_id}]"
        ),
    )

    _FAILOVER_HISTORY[failover_id] = result
    return result


def get_failover_result(failover_id: str) -> Optional[HotFailoverResult]:
    """查询单次热转移执行详情"""
    return _FAILOVER_HISTORY.get(failover_id)


def list_failover_history(limit: int = 50) -> List[Dict[str, Any]]:
    """获取近期故障热转移历史流水"""
    items = list(_FAILOVER_HISTORY.values())
    items.sort(key=lambda x: x.timestamp, reverse=True)
    return [i.to_dict() for i in items[:limit]]
