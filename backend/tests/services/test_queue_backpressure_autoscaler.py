"""Unit tests for D1.2 Queue Backpressure Autoscaler Service."""

from datetime import datetime, timedelta, timezone
import pytest

from app.services.queue_backpressure_autoscaler import (
    HpaPolicyConfig,
    HpaScalingDirection,
    QueueBackpressureMetrics,
    evaluate_hpa_decision,
    get_hpa_policy,
    list_hpa_history,
    list_hpa_policies,
    mark_policy_scaled,
    register_hpa_policy,
    reset_hpa_registry,
)


@pytest.fixture(autouse=True)
def clean_registry():
    reset_hpa_registry()
    yield
    reset_hpa_registry()


def test_hpa_policy_validation():
    # min_replicas < 1
    with pytest.raises(ValueError, match="min_replicas 至少为 1"):
        HpaPolicyConfig(policy_id="test", min_replicas=0).validate()

    # max_replicas < min_replicas
    with pytest.raises(ValueError, match="max_replicas 不能小于 min_replicas"):
        HpaPolicyConfig(policy_id="test", min_replicas=5, max_replicas=2).validate()

    # 合法策略注册
    policy = HpaPolicyConfig(
        policy_id="hpa_default",
        target_queue="default",
        min_replicas=2,
        max_replicas=10,
        target_concurrency_per_pod=5,
        target_latency_slo_sec=10.0,
    )
    register_hpa_policy(policy)

    assert get_hpa_policy("hpa_default") == policy
    assert len(list_hpa_policies()) == 1


def test_hpa_evaluate_idle_scale_down():
    policy = HpaPolicyConfig(
        policy_id="hpa_idle_test",
        target_queue="default",
        min_replicas=1,
        max_replicas=10,
        target_concurrency_per_pod=5,
    )
    register_hpa_policy(policy)

    # 当前有 5 个副本，但队列完全空闲 (0 排队, 0 运行)
    metrics = QueueBackpressureMetrics(
        queue_name="default",
        current_queue_depth=0,
        running_tasks_count=0,
        p95_queue_latency_sec=1.0,
        current_replicas=5,
    )

    decision = evaluate_hpa_decision("hpa_idle_test", metrics)
    assert decision.direction == HpaScalingDirection.SCALE_DOWN
    assert decision.desired_replicas == 1
    assert decision.replicas_delta == -4
    assert "缩容至最小保底副本数 1" in decision.reason


def test_hpa_evaluate_heavy_backpressure_scale_up():
    policy = HpaPolicyConfig(
        policy_id="hpa_heavy_test",
        target_queue="default",
        min_replicas=1,
        max_replicas=20,
        target_concurrency_per_pod=5,
        target_latency_slo_sec=10.0,
    )
    register_hpa_policy(policy)

    # 35 个积压任务，P95 时延 30s (超标 3x)
    metrics = QueueBackpressureMetrics(
        queue_name="default",
        current_queue_depth=30,
        running_tasks_count=5,
        p95_queue_latency_sec=30.0,
        current_replicas=2,
    )

    decision = evaluate_hpa_decision("hpa_heavy_test", metrics)
    assert decision.direction == HpaScalingDirection.SCALE_UP
    # base = 35 / 5 = 7. latency penalty = (30/10) - 1 = 2.0. factor = 1 + 0.5*2.0 = 2.0. raw = ceil(7 * 2.0) = 14
    assert decision.desired_replicas == 14
    assert decision.replicas_delta == 12
    assert "P95时延 30.0s" in decision.reason


def test_hpa_max_replicas_clamped():
    policy = HpaPolicyConfig(
        policy_id="hpa_clamp_test",
        target_queue="default",
        min_replicas=1,
        max_replicas=15,
        target_concurrency_per_pod=5,
        target_latency_slo_sec=10.0,
    )
    register_hpa_policy(policy)

    # 海量积压 500 个任务
    metrics = QueueBackpressureMetrics(
        queue_name="default",
        current_queue_depth=500,
        running_tasks_count=50,
        p95_queue_latency_sec=100.0,
        current_replicas=5,
    )

    decision = evaluate_hpa_decision("hpa_clamp_test", metrics)
    assert decision.direction == HpaScalingDirection.SCALE_UP
    # 必须夹紧在 max_replicas 15
    assert decision.desired_replicas == 15
    assert decision.replicas_delta == 10


def test_hpa_cooldown_stabilization_suppresses_scale_down():
    policy = HpaPolicyConfig(
        policy_id="hpa_cooldown_test",
        target_queue="default",
        min_replicas=1,
        max_replicas=10,
        target_concurrency_per_pod=5,
        scale_down_stabilization_sec=60.0,
    )
    register_hpa_policy(policy)

    now = datetime.now(timezone.utc)
    # 模拟 20 秒前刚执行过一次扩容
    mark_policy_scaled("hpa_cooldown_test", scaled_at=now - timedelta(seconds=20))

    # 队列突然变空，本应缩容到 1
    metrics = QueueBackpressureMetrics(
        queue_name="default",
        current_queue_depth=0,
        running_tasks_count=0,
        p95_queue_latency_sec=0.5,
        current_replicas=6,
    )

    decision = evaluate_hpa_decision("hpa_cooldown_test", metrics, now=now)
    # 必须被冷却窗口抑制，维持 6 个副本
    assert decision.direction == HpaScalingDirection.MAINTAIN
    assert decision.desired_replicas == 6
    assert decision.replicas_delta == 0
    assert "抑制缩容" in decision.reason

    # 决策被记入历史
    history = list_hpa_history(policy_id="hpa_cooldown_test")
    assert len(history) == 1
