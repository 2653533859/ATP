"""云原生 Worker 动态扩缩容与集群配额仲裁单元测试 (T1.1)。"""

from __future__ import annotations

import pytest
from app.services.elastic_test_worker_autoscaler import (
    ClusterQuotaConfig,
    QuotaArbitrationStatus,
    ScalingAction,
    apply_autoscaling_decision,
    clear_autoscaler_state,
    evaluate_autoscaling,
    get_current_cluster_status,
    list_scaling_events,
)


@pytest.fixture(autouse=True)
def _reset_autoscaler_state():
    clear_autoscaler_state()
    yield
    clear_autoscaler_state()


def test_evaluate_autoscaling_noop():
    """测试当前负载适中时无操作 (NOOP)。"""
    # 2 个 worker，单个并发 4，队列 8 时，期望 8 / 4 = 2，无需扩缩
    decision = evaluate_autoscaling(queue_depth=8, current_replicas=2)
    assert decision.action == ScalingAction.NOOP
    assert decision.current_replicas == 2
    assert decision.desired_replicas == 2
    assert decision.allocated_replicas == 2
    assert decision.arbitration_status == QuotaArbitrationStatus.SUFFICIENT


def test_evaluate_autoscaling_scale_up():
    """测试队列积压时触发动态扩容 (SCALE_UP)。"""
    # 队列 24，单个并发 4，期望 6 副本
    decision = evaluate_autoscaling(queue_depth=24, current_replicas=2)
    assert decision.action == ScalingAction.SCALE_UP
    assert decision.current_replicas == 2
    assert decision.desired_replicas == 6
    assert decision.allocated_replicas == 6
    assert decision.arbitration_status == QuotaArbitrationStatus.SUFFICIENT
    assert decision.cpu_utilization_estimate_pct > 0


def test_evaluate_autoscaling_scale_down():
    """测试队列空闲时触发平滑缩容 (SCALE_DOWN)。"""
    decision = evaluate_autoscaling(queue_depth=0, current_replicas=5)
    assert decision.action == ScalingAction.SCALE_DOWN
    assert decision.current_replicas == 5
    assert decision.desired_replicas == 1
    assert decision.allocated_replicas == 1


def test_evaluate_autoscaling_quota_exhausted():
    """测试当集群硬件物理上限已满时阻断扩容 (QUOTA_BLOCKED)。"""
    # 限制集群仅有 2 核 CPU，每个 Pod 0.5 核，最多容纳 4 个 Pod
    cfg = ClusterQuotaConfig(allocatable_cpu_cores=2.0, worker_request_cpu=0.5)
    decision = evaluate_autoscaling(queue_depth=50, current_replicas=4, config=cfg)
    assert decision.action == ScalingAction.QUOTA_BLOCKED
    assert decision.arbitration_status == QuotaArbitrationStatus.EXHAUSTED
    assert decision.allocated_replicas == 4


def test_evaluate_autoscaling_arbitrated_degraded():
    """测试期望副本超出集群容量时降级至最大可用容量 (ARBITRATED_DEGRADED)。"""
    # 集群限额 6 个 Pod，队列期望 10 个 Pod，应降级扩容至 6
    cfg = ClusterQuotaConfig(allocatable_cpu_cores=3.0, worker_request_cpu=0.5)
    decision = evaluate_autoscaling(queue_depth=40, current_replicas=2, config=cfg)
    assert decision.action == ScalingAction.SCALE_UP
    assert decision.arbitration_status == QuotaArbitrationStatus.ARBITRATED_DEGRADED
    assert decision.desired_replicas == 10
    assert decision.allocated_replicas == 6


def test_apply_autoscaling_decision():
    """测试执行落地扩缩容指令并记录审计事件。"""
    decision = evaluate_autoscaling(queue_depth=20, current_replicas=2)
    res = apply_autoscaling_decision(decision)

    assert res["status"] == "APPLIED"
    assert res["active_replicas"] == 5

    status = get_current_cluster_status()
    assert status["current_active_replicas"] == 5
    assert status["total_scaling_events"] == 1

    events = list_scaling_events()
    assert len(events) == 1
    assert events[0]["action"] == "SCALE_UP"
