"""Unit tests for C1.1 Cluster Worker Node Dynamic Load Monitoring & Capacity Scoring.

Tests:
1. ClusterWorkerNode weighted load scoring and available capacity index calculation
2. Node capacity tier classification (HEALTHY_IDLE, MODERATE_LOAD, OVERLOADED, OFFLINE)
3. Worker heartbeat registration and alive expiration
4. select_optimal_worker selects node with maximum available capacity for matching queue
5. select_optimal_worker respects queue subscriptions, excluded nodes, and capacity limits
6. get_cluster_capacity_overview computes aggregate utilization and health distribution
"""

from __future__ import annotations

from datetime import datetime, timezone
import pytest

from app.services.cluster_load_balancer import (
    _CLUSTER_NODES,
    ClusterWorkerNode,
    get_cluster_capacity_overview,
    list_cluster_nodes,
    register_worker_heartbeat,
    select_optimal_worker,
)


@pytest.fixture(autouse=True)
def clean_cluster_nodes():
    _CLUSTER_NODES.clear()
    yield
    _CLUSTER_NODES.clear()


def test_cluster_worker_node_load_and_capacity_scoring():
    # 1. Idle node: 0 tasks, 10% CPU, 20% Mem -> low load, high capacity
    idle_node = ClusterWorkerNode(
        worker_id="node_idle_01",
        hostname="worker-01",
        ip_address="192.168.1.10",
        current_concurrency=0,
        max_concurrency=10,
        cpu_usage_pct=10.0,
        memory_usage_pct=20.0,
    )
    # Expected load: 0.5*0 + 0.3*10 + 0.2*20 = 7.0
    assert idle_node.calculate_load_score() == 7.0
    # Expected capacity: 100 - 7 = 93.0
    assert idle_node.calculate_capacity_score() == 93.0
    assert idle_node.capacity_level == "HEALTHY_IDLE"

    # 2. Busy node: 8/10 tasks (80%), 70% CPU, 60% Mem
    busy_node = ClusterWorkerNode(
        worker_id="node_busy_01",
        hostname="worker-02",
        ip_address="192.168.1.11",
        current_concurrency=8,
        max_concurrency=10,
        cpu_usage_pct=70.0,
        memory_usage_pct=60.0,
    )
    # Expected load: 0.5*80 + 0.3*70 + 0.2*60 = 40 + 21 + 12 = 73.0
    assert busy_node.calculate_load_score() == 73.0
    # Expected capacity: 100 - 73 = 27.0
    assert busy_node.calculate_capacity_score() == 27.0
    assert busy_node.capacity_level == "HEAVY_LOAD"

    # 3. Saturated node: 10/10 tasks (100% full capacity penalty)
    full_node = ClusterWorkerNode(
        worker_id="node_full_01",
        hostname="worker-03",
        ip_address="192.168.1.12",
        current_concurrency=10,
        max_concurrency=10,
        cpu_usage_pct=90.0,
        memory_usage_pct=85.0,
    )
    assert full_node.calculate_load_score() >= 100.0
    assert full_node.calculate_capacity_score() == 0.0
    assert full_node.capacity_level == "OVERLOADED"


def test_register_worker_heartbeat():
    node = register_worker_heartbeat(
        worker_id="worker_test_reg_01",
        hostname="shanghai-prod-w01",
        ip_address="10.0.1.25",
        queues=["default", "performance"],
        current_concurrency=2,
        max_concurrency=16,
        cpu_usage_pct=15.0,
        memory_usage_pct=30.0,
    )
    assert node.worker_id == "worker_test_reg_01"
    assert node.hostname == "shanghai-prod-w01"
    assert "performance" in node.queues
    assert node.is_alive is True

    # Refresh heartbeat with higher load
    updated = register_worker_heartbeat(
        worker_id="worker_test_reg_01",
        hostname="shanghai-prod-w01",
        ip_address="10.0.1.25",
        current_concurrency=5,
        max_concurrency=16,
        cpu_usage_pct=35.0,
        memory_usage_pct=40.0,
    )
    assert updated.current_concurrency == 5
    assert updated.cpu_usage_pct == 35.0


def test_select_optimal_worker():
    # Setup 3 worker nodes
    # Node A: heavily loaded on 'performance'
    register_worker_heartbeat(
        worker_id="node_perf_heavy",
        hostname="w-heavy",
        ip_address="10.0.1.10",
        queues=["performance"],
        current_concurrency=9,
        max_concurrency=10,
        cpu_usage_pct=80.0,
        memory_usage_pct=80.0,
    )

    # Node B: lightly loaded on 'performance'
    register_worker_heartbeat(
        worker_id="node_perf_light",
        hostname="w-light",
        ip_address="10.0.1.11",
        queues=["performance"],
        current_concurrency=1,
        max_concurrency=10,
        cpu_usage_pct=15.0,
        memory_usage_pct=25.0,
    )

    # Node C: idle but only subscribes to 'mobile'
    register_worker_heartbeat(
        worker_id="node_mobile_idle",
        hostname="w-mobile",
        ip_address="10.0.1.12",
        queues=["mobile_special"],
        current_concurrency=0,
        max_concurrency=5,
    )

    # 1. Dispatch to 'performance' queue -> should pick node_perf_light
    optimal = select_optimal_worker(required_queue="performance")
    assert optimal is not None
    assert optimal.worker_id == "node_perf_light"

    # 2. Exclude node_perf_light -> should fall back to node_perf_heavy
    fallback = select_optimal_worker(required_queue="performance", exclude_worker_ids=["node_perf_light"])
    assert fallback is not None
    assert fallback.worker_id == "node_perf_heavy"

    # 3. Dispatch to 'mobile_special' queue -> should pick node_mobile_idle
    mobile_optimal = select_optimal_worker(required_queue="mobile_special")
    assert mobile_optimal is not None
    assert mobile_optimal.worker_id == "node_mobile_idle"

    # 4. Dispatch to non-existent queue -> should return None
    none_node = select_optimal_worker(required_queue="non_existent_queue")
    assert none_node is None


def test_get_cluster_capacity_overview():
    # 1. Register an active node
    register_worker_heartbeat(
        worker_id="node_live_01",
        hostname="w-live",
        ip_address="10.0.1.20",
        current_concurrency=2,
        max_concurrency=10,
        status="online",
    )

    # 2. Register an expired node with old timestamp
    old_ts = datetime.now(timezone.utc).timestamp() - 100.0
    register_worker_heartbeat(
        worker_id="node_expired_old",
        hostname="w-dead",
        ip_address="10.0.1.99",
        status="online",
    )
    dead_node = [n for n in list_cluster_nodes(only_alive=False) if n.worker_id == "node_expired_old"][0]
    dead_node.heartbeat_timestamp = old_ts

    overview = get_cluster_capacity_overview()
    assert overview["total_nodes_registered"] == 2
    assert overview["total_alive_nodes"] == 1
    assert overview["total_concurrency_slots"] == 10
    assert overview["total_active_tasks"] == 2
    assert overview["cluster_utilization_pct"] == 20.0
    assert overview["health_distribution"]["OFFLINE"] == 1
    assert overview["health_distribution"]["HEALTHY_IDLE"] == 1
