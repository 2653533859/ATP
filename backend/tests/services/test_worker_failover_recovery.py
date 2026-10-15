"""Unit tests for C1.3 Worker Node Disconnection Detection, Heartbeat Timeout & Task Failover.

Tests:
1. detect_dead_workers identifies nodes with expired heartbeats and marks them offline
2. failover_worker_tasks rescues running orphan tasks and reschedules them to healthy nodes
3. Tasks reaching maximum failover retries are safely aborted
4. scan_and_recover_dead_workers sweeps cluster and logs failover history
"""

from __future__ import annotations

from datetime import datetime, timezone
import pytest

from app.services.adaptive_queue_preemptor import (
    _TASKS,
    enqueue_task,
)
from app.services.cluster_load_balancer import (
    _CLUSTER_NODES,
    register_worker_heartbeat,
)
from app.services.worker_failover_recovery import (
    _FAILOVER_HISTORY,
    detect_dead_workers,
    failover_worker_tasks,
    list_failover_history,
    scan_and_recover_dead_workers,
)


@pytest.fixture(autouse=True)
def clean_state():
    _CLUSTER_NODES.clear()
    _TASKS.clear()
    _FAILOVER_HISTORY.clear()
    yield
    _CLUSTER_NODES.clear()
    _TASKS.clear()
    _FAILOVER_HISTORY.clear()


def test_detect_dead_workers_heartbeat_timeout():
    # 1. Register alive node
    alive_node = register_worker_heartbeat(
        worker_id="node_healthy",
        hostname="worker-healthy",
        ip_address="10.0.0.1",
        status="online",
    )

    # 2. Register dead node with old heartbeat (60s ago > 30s timeout)
    dead_node = register_worker_heartbeat(
        worker_id="node_timeout",
        hostname="worker-dead",
        ip_address="10.0.0.2",
        status="online",
        current_concurrency=3,
    )
    dead_node.heartbeat_timestamp = datetime.now(timezone.utc).timestamp() - 60.0

    dead_list = detect_dead_workers(timeout_seconds=30.0)
    assert len(dead_list) == 1
    assert dead_list[0].worker_id == "node_timeout"
    assert dead_list[0].status == "offline"
    assert dead_list[0].current_concurrency == 0

    # Healthy node remains online
    assert alive_node.status == "online"


def test_failover_worker_tasks_rescheduling():
    # Setup healthy backup worker
    register_worker_heartbeat(
        worker_id="worker_backup",
        hostname="backup-worker",
        ip_address="10.0.0.10",
        queues=["default"],
        current_concurrency=0,
        max_concurrency=5,
    )

    # Setup crashing worker
    register_worker_heartbeat(
        worker_id="worker_crashing",
        hostname="crash-worker",
        ip_address="10.0.0.11",
        queues=["default"],
        current_concurrency=0,
        max_concurrency=5,
    )

    # Enqueue a task directly assigned to worker_crashing
    task, _ = enqueue_task("订单微服务压力测试", queue_name="default", priority="P1")
    # Manually pin to crashing worker to simulate crash mid-flight
    task.assigned_worker_id = "worker_crashing"
    task.status = "running"

    # Trigger failover for worker_crashing
    report = failover_worker_tasks("worker_crashing", max_retries=3)

    assert report.orphaned_tasks_count == 1
    assert report.recovered_tasks_count == 1
    assert report.permanently_failed_count == 0
    assert task.task_id in report.recovered_task_ids

    # Task should be retried and rescheduled onto worker_backup!
    assert task.retry_count == 1
    assert task.last_failed_worker_id == "worker_crashing"
    assert task.status == "running"
    assert task.assigned_worker_id == "worker_backup"


def test_failover_exceeding_max_retries():
    # Setup crashing worker
    register_worker_heartbeat(
        worker_id="worker_flaky",
        hostname="flaky-worker",
        ip_address="10.0.0.12",
        queues=["default"],
    )

    task, _ = enqueue_task("高重试超限任务", queue_name="default", priority="P2")
    task.assigned_worker_id = "worker_flaky"
    task.status = "running"
    task.retry_count = 3  # Already failed 3 times

    # Trigger failover with max_retries=3
    report = failover_worker_tasks("worker_flaky", max_retries=3)

    assert report.orphaned_tasks_count == 1
    assert report.recovered_tasks_count == 0
    assert report.permanently_failed_count == 1
    assert task.status == "aborted"


def test_scan_and_recover_dead_workers():
    # Setup worker that died with stranded task
    dead_worker = register_worker_heartbeat(
        worker_id="worker_unresponsive",
        hostname="unresponsive",
        ip_address="10.0.0.99",
        queues=["default"],
    )
    dead_worker.heartbeat_timestamp = datetime.now(timezone.utc).timestamp() - 50.0

    task, _ = enqueue_task("未响应节点悬挂任务", queue_name="default", priority="P2")
    task.assigned_worker_id = "worker_unresponsive"
    task.status = "running"

    reports = scan_and_recover_dead_workers(timeout_seconds=30.0)
    assert len(reports) == 1
    assert reports[0].dead_worker_id == "worker_unresponsive"
    assert reports[0].recovered_tasks_count == 1

    history = list_failover_history()
    assert len(history) == 1
    assert history[0].dead_worker_id == "worker_unresponsive"
