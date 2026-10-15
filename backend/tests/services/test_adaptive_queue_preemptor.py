"""Unit tests for C1.2 Adaptive Task Priority Queue & Preemptive Scheduling Engine.

Tests:
1. Immediate dispatch when worker slots are available
2. Normal queuing when cluster is saturated with same/lower priority
3. Elastic preemption: P0/P1 high-priority task preempts low-priority P3 task
4. Automated task resumption: completing a task immediately wakes up suspended tasks
5. Queue position and ETA waiting time estimation algorithm
"""

from __future__ import annotations

import pytest

from app.services.adaptive_queue_preemptor import (
    _TASKS,
    calculate_queue_eta_seconds,
    complete_task,
    enqueue_task,
    list_queued_tasks,
)
from app.services.cluster_load_balancer import (
    _CLUSTER_NODES,
    register_worker_heartbeat,
)


@pytest.fixture(autouse=True)
def clean_registry():
    _CLUSTER_NODES.clear()
    _TASKS.clear()
    yield
    _CLUSTER_NODES.clear()
    _TASKS.clear()


def test_immediate_dispatch_when_capacity_available():
    # 1. Register a worker with 2 slots on 'api' queue
    register_worker_heartbeat(
        worker_id="w_api_01",
        hostname="api-worker-1",
        ip_address="10.0.0.1",
        queues=["api"],
        current_concurrency=0,
        max_concurrency=2,
    )

    # 2. Enqueue normal P2 task
    task, preempted = enqueue_task(
        "API 冒烟测试任务 01",
        queue_name="api",
        priority="P2",
    )
    assert preempted is False
    assert task.status == "running"
    assert task.assigned_worker_id == "w_api_01"


def test_saturated_cluster_queuing_and_preemption():
    # 1. Register a worker with capacity of 1 slot
    register_worker_heartbeat(
        worker_id="w_single_slot",
        hostname="single-worker",
        ip_address="10.0.0.2",
        queues=["default"],
        current_concurrency=0,
        max_concurrency=1,
    )

    # 2. First task: P3 batch task (occupies the only slot)
    t_low, p_low = enqueue_task(
        "夜间数据归档任务 (P3)",
        queue_name="default",
        priority="P3",
        estimated_duration_sec=60.0,
    )
    assert p_low is False
    assert t_low.status == "running"
    assert t_low.assigned_worker_id == "w_single_slot"

    # 3. Second task: P2 task arrives -> cluster is saturated, cannot preempt P3 because P2 doesn't have enough privilege
    t_med, p_med = enqueue_task(
        "常规回归测试 (P2)",
        queue_name="default",
        priority="P2",
    )
    assert p_med is False
    assert t_med.status == "queued"

    # 4. Third task: Emergency P0 task arrives -> PREEMPTS running P3 task!
    t_high, p_high = enqueue_task(
        "线上支付阻断紧急冒烟 (P0)",
        queue_name="default",
        priority="P0",
    )
    assert p_high is True
    assert t_high.status == "running"
    assert t_high.assigned_worker_id == "w_single_slot"

    # Check victim P3 task is now suspended
    assert t_low.status == "suspended"
    assert t_low.preempted_count == 1
    assert t_low.preempted_by_task_id == t_high.task_id


def test_complete_task_and_resume_suspended():
    register_worker_heartbeat(
        worker_id="w_test_resume",
        hostname="resume-worker",
        ip_address="10.0.0.3",
        queues=["default"],
        current_concurrency=0,
        max_concurrency=1,
    )

    # P3 task runs
    t_p3, _ = enqueue_task("P3 Task", queue_name="default", priority="P3")
    # P0 task preempts P3
    t_p0, p0_preempted = enqueue_task("P0 Task", queue_name="default", priority="P0")
    assert p0_preempted is True
    assert t_p3.status == "suspended"

    # Complete P0 task
    complete_task(t_p0.task_id, status="completed")
    assert t_p0.status == "completed"

    # Suspended P3 task should be automatically resumed!
    assert t_p3.status == "running"
    assert t_p3.assigned_worker_id == "w_test_resume"


def test_queue_eta_calculation():
    register_worker_heartbeat(
        worker_id="w_eta_worker",
        hostname="eta-worker",
        ip_address="10.0.0.4",
        queues=["queue_eta"],
        current_concurrency=0,
        max_concurrency=1,  # 1 slot
    )

    # Task 1: running
    t1, _ = enqueue_task("Running Task", queue_name="queue_eta", priority="P1", estimated_duration_sec=20.0)
    assert t1.status == "running"
    eta_t1 = calculate_queue_eta_seconds(t1.task_id)
    assert eta_t1["estimated_wait_seconds"] == 0.0

    # Task 2: queued ahead
    t2, _ = enqueue_task("Queued Task 1", queue_name="queue_eta", priority="P1", estimated_duration_sec=30.0)
    assert t2.status == "queued"
    t3, _ = enqueue_task("Queued Task 2", queue_name="queue_eta", priority="P2", estimated_duration_sec=40.0)

    eta_t3 = calculate_queue_eta_seconds(t3.task_id)
    assert eta_t3["queue_position"] == 2
    assert eta_t3["estimated_wait_seconds"] >= 30.0  # At least wait for Task 2's 30s
    assert "排在队列第 2 位" in eta_t3["message"]

    all_tasks = list_queued_tasks(queue_name="queue_eta")
    assert len(all_tasks) == 3
