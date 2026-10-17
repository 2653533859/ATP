"""工作流执行死循环与超时熔断看门狗单测 (T4.1)"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
import pytest

from app.services.workflow_execution_sandbox_guard import (
    ExcessiveFailuresCircuitBreakError,
    InfiniteLoopDetectedError,
    SandboxGuardPolicy,
    WorkflowSandboxWatchdog,
    WorkflowTimeoutCircuitBreakError,
    clear_guard_violations,
    list_guard_violations,
)


@pytest.fixture(autouse=True)
def clean_state():
    clear_guard_violations()
    yield
    clear_guard_violations()


def test_infinite_loop_detection():
    policy = SandboxGuardPolicy(max_loop_iterations_per_node=5)
    dog = WorkflowSandboxWatchdog("wf_loop", "run_1", policy=policy)

    # 前 5 次正常
    for _ in range(5):
        dog.check_before_node_execution("node_retry")

    # 第 6 次超过阈值触发 InfiniteLoopDetectedError
    with pytest.raises(InfiniteLoopDetectedError, match="检测到死循环异常"):
        dog.check_before_node_execution("node_retry")

    assert dog.is_circuit_broken is True
    assert len(list_guard_violations()) == 1


def test_global_timeout_circuit_breaker():
    policy = SandboxGuardPolicy(max_total_timeout_seconds=10.0)
    now = datetime.now(timezone.utc)
    dog = WorkflowSandboxWatchdog("wf_timeout", "run_2", policy=policy, now=now)

    # 模拟在 15 秒后执行下一个节点
    future_time = now + timedelta(seconds=15)
    with pytest.raises(WorkflowTimeoutCircuitBreakError, match="执行超时熔断"):
        dog.check_before_node_execution("node_slow", now=future_time)

    assert dog.is_circuit_broken is True


def test_consecutive_failures_circuit_breaker():
    policy = SandboxGuardPolicy(max_consecutive_failures=3)
    dog = WorkflowSandboxWatchdog("wf_fail", "run_3", policy=policy)

    # 连续记录 3 次失败
    dog.record_after_node_execution("node_1", success=False, duration_ms=50.0)
    dog.record_after_node_execution("node_2", success=False, duration_ms=50.0)
    dog.record_after_node_execution("node_3", success=False, duration_ms=50.0)

    # 执行第 4 个节点前触发熔断
    with pytest.raises(ExcessiveFailuresCircuitBreakError, match="连续失败熔断"):
        dog.check_before_node_execution("node_4")
