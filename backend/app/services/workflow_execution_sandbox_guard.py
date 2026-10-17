"""工作流执行死循环与超时熔断看门狗服务 (T4.1)

保护 Celery Worker 进程与平台调度执行器免受恶意或错误配置破坏:
1. 节点循环上限防护 (Infinite Loop Detection): 监控单节点访问频次, 超出阈值立即阻断;
2. 全链路时延熔断看门狗 (Global Workflow Timeout Watchdog);
3. 单节点超时阈值防护 (Node Execution Timeout Guard);
4. 连续故障快速熔断 (Consecutive Failure Circuit Breaker)。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional


class GuardViolationType(str, Enum):
    INFINITE_LOOP = "INFINITE_LOOP"
    GLOBAL_TIMEOUT = "GLOBAL_TIMEOUT"
    NODE_TIMEOUT = "NODE_TIMEOUT"
    CONSECUTIVE_FAILURES = "CONSECUTIVE_FAILURES"


class WorkflowSandboxException(Exception):
    """工作流沙箱保护基础异常"""

    def __init__(self, message: str, violation_type: GuardViolationType):
        super().__init__(message)
        self.violation_type = violation_type


class InfiniteLoopDetectedError(WorkflowSandboxException):
    def __init__(self, node_id: str, count: int, max_allowed: int):
        super().__init__(
            f"检测到死循环异常 (Infinite Loop): 节点 [{node_id}] 执行次数达到 [{count}] 次，超过沙箱上限 [{max_allowed}] 次，已紧急熔断",
            GuardViolationType.INFINITE_LOOP,
        )
        self.node_id = node_id
        self.count = count


class WorkflowTimeoutCircuitBreakError(WorkflowSandboxException):
    def __init__(self, elapsed_seconds: float, max_allowed: float):
        super().__init__(
            f"工作流执行超时熔断: 累计耗时 [{elapsed_seconds:.1f}s] 超过全链路最大安全限制 [{max_allowed:.1f}s]",
            GuardViolationType.GLOBAL_TIMEOUT,
        )
        self.elapsed_seconds = elapsed_seconds


class ExcessiveFailuresCircuitBreakError(WorkflowSandboxException):
    def __init__(self, consecutive_failures: int, threshold: int):
        super().__init__(
            f"工作流连续失败熔断: 连续 [{consecutive_failures}] 个节点失败，达到故障熔断阈值 [{threshold}]",
            GuardViolationType.CONSECUTIVE_FAILURES,
        )


@dataclass
class SandboxGuardPolicy:
    max_total_timeout_seconds: float = 300.0  # 全链路超时熔断阈值
    max_node_timeout_seconds: float = 60.0  # 单节点超时阈值
    max_loop_iterations_per_node: int = 50  # 单节点最大迭代次数 (防死循环)
    max_consecutive_failures: int = 5  # 连续报错熔断阈值

    def to_dict(self) -> Dict[str, Any]:
        return {
            "max_total_timeout_seconds": self.max_total_timeout_seconds,
            "max_node_timeout_seconds": self.max_node_timeout_seconds,
            "max_loop_iterations_per_node": self.max_loop_iterations_per_node,
            "max_consecutive_failures": self.max_consecutive_failures,
        }


@dataclass
class GuardViolationRecord:
    violation_id: str
    workflow_id: str
    run_id: str
    violation_type: GuardViolationType
    message: str
    node_id: Optional[str]
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def to_dict(self) -> Dict[str, Any]:
        return {
            "violation_id": self.violation_id,
            "workflow_id": self.workflow_id,
            "run_id": self.run_id,
            "violation_type": self.violation_type.value,
            "message": self.message,
            "node_id": self.node_id,
            "timestamp": self.timestamp,
        }


# 全局轻量级违规告警记录
_VIOLATION_STORE: List[GuardViolationRecord] = []


def clear_guard_violations() -> None:
    _VIOLATION_STORE.clear()


def list_guard_violations(limit: int = 50) -> List[Dict[str, Any]]:
    return [v.to_dict() for v in reversed(_VIOLATION_STORE[-limit:])]


class WorkflowSandboxWatchdog:
    """单个工作流运行实例的沙箱看门狗守卫"""

    def __init__(
        self,
        workflow_id: str,
        run_id: str,
        policy: Optional[SandboxGuardPolicy] = None,
        now: Optional[datetime] = None,
    ):
        self.workflow_id = workflow_id
        self.run_id = run_id
        self.policy = policy or SandboxGuardPolicy()
        self.start_time = now or datetime.now(timezone.utc)
        self.node_visit_counts: Dict[str, int] = {}
        self.consecutive_failures = 0
        self.total_nodes_executed = 0
        self.is_circuit_broken = False
        self.break_reason: Optional[str] = None

    def check_before_node_execution(self, node_id: str, now: Optional[datetime] = None) -> None:
        """在节点执行前进行沙箱配额检查，违规直接熔断阻断"""
        current_time = now or datetime.now(timezone.utc)
        elapsed = (current_time - self.start_time).total_seconds()

        # 1. 检查全链路总超时
        if elapsed > self.policy.max_total_timeout_seconds:
            self._record_violation(GuardViolationType.GLOBAL_TIMEOUT, f"全链路总超时 {elapsed:.1f}s", node_id)
            raise WorkflowTimeoutCircuitBreakError(elapsed, self.policy.max_total_timeout_seconds)

        # 2. 检查连续故障熔断
        if self.consecutive_failures >= self.policy.max_consecutive_failures:
            self._record_violation(
                GuardViolationType.CONSECUTIVE_FAILURES, f"连续失败 {self.consecutive_failures} 个节点", node_id
            )
            raise ExcessiveFailuresCircuitBreakError(self.consecutive_failures, self.policy.max_consecutive_failures)

        # 3. 检查单节点死循环迭代次数
        visits = self.node_visit_counts.get(node_id, 0) + 1
        self.node_visit_counts[node_id] = visits
        if visits > self.policy.max_loop_iterations_per_node:
            self._record_violation(
                GuardViolationType.INFINITE_LOOP,
                f"单节点迭代超过 {self.policy.max_loop_iterations_per_node} 次",
                node_id,
            )
            raise InfiniteLoopDetectedError(node_id, visits, self.policy.max_loop_iterations_per_node)

    def record_after_node_execution(
        self,
        node_id: str,
        success: bool,
        duration_ms: float,
    ) -> None:
        """记录节点执行完成结果与时延状态"""
        self.total_nodes_executed += 1

        # 检查单节点耗时是否超标
        duration_sec = duration_ms / 1000.0
        if duration_sec > self.policy.max_node_timeout_seconds:
            self._record_violation(GuardViolationType.NODE_TIMEOUT, f"单节点执行耗时 {duration_sec:.1f}s 超标", node_id)

        if success:
            self.consecutive_failures = 0
        else:
            self.consecutive_failures += 1

    def _record_violation(self, vtype: GuardViolationType, message: str, node_id: Optional[str]) -> None:
        self.is_circuit_broken = True
        self.break_reason = message
        record = GuardViolationRecord(
            violation_id=f"viol_{len(_VIOLATION_STORE) + 1}",
            workflow_id=self.workflow_id,
            run_id=self.run_id,
            violation_type=vtype,
            message=message,
            node_id=node_id,
        )
        _VIOLATION_STORE.append(record)
