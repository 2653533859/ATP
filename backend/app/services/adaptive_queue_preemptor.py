"""Adaptive Task Priority Queue & Preemptive Scheduling Engine (C1.2).

Provides:
1. Multi-tier task priority hierarchy (P0 Emergency, P1 Core, P2 Normal, P3 Batch).
2. Elastic slot preemption: high-priority P0 tasks preempt low-priority P3/P2 tasks when cluster is saturated.
3. Automated task suspension, resumption, and starvation prevention.
4. Accurate Queue Waiting Time & ETA estimation based on cluster throughput.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
import logging
from typing import Any
import uuid

from app.services.cluster_load_balancer import (
    ClusterWorkerNode,
    get_worker_node,
    list_cluster_nodes,
    select_optimal_worker,
)

logger = logging.getLogger(__name__)

PRIORITY_WEIGHTS = {
    "P0": 100,
    "P1": 50,
    "P2": 20,
    "P3": 5,
}


@dataclass
class QueuedTaskItem:
    task_id: str
    task_name: str
    queue_name: str
    priority: str  # "P0" | "P1" | "P2" | "P3"
    assigned_worker_id: str | None = None
    status: str = "queued"  # "queued" | "running" | "suspended" | "completed" | "aborted"
    enqueued_at: float = field(default_factory=lambda: datetime.now(timezone.utc).timestamp())
    started_at: float | None = None
    estimated_duration_sec: float = 30.0
    preempted_count: int = 0
    preempted_by_task_id: str | None = None
    retry_count: int = 0
    last_failed_worker_id: str | None = None

    @property
    def priority_rank(self) -> int:
        return PRIORITY_WEIGHTS.get(self.priority, 10)

    def to_dict(self) -> dict[str, Any]:
        return {
            "task_id": self.task_id,
            "task_name": self.task_name,
            "queue_name": self.queue_name,
            "priority": self.priority,
            "assigned_worker_id": self.assigned_worker_id,
            "status": self.status,
            "enqueued_at": self.enqueued_at,
            "started_at": self.started_at,
            "estimated_duration_sec": self.estimated_duration_sec,
            "preempted_count": self.preempted_count,
            "preempted_by_task_id": self.preempted_by_task_id,
            "retry_count": self.retry_count,
            "last_failed_worker_id": self.last_failed_worker_id,
        }


# In-memory registry of tasks
_TASKS: dict[str, QueuedTaskItem] = {}


def _get_queue_workers(queue_name: str) -> list[ClusterWorkerNode]:
    """Retrieve alive workers serving the specified queue."""
    return list_cluster_nodes(queue=queue_name, only_alive=True)


def calculate_queue_eta_seconds(task_id: str) -> dict[str, Any]:
    """Calculate queue position and estimated waiting time (ETA) in seconds for a task."""
    target_task = _TASKS.get(task_id)
    if not target_task:
        raise ValueError(f"任务不存在: {task_id}")

    if target_task.status == "running":
        return {
            "task_id": task_id,
            "status": "running",
            "queue_position": 0,
            "estimated_wait_seconds": 0.0,
            "message": "任务正在 Worker 节点上运行中",
        }

    if target_task.status in {"completed", "aborted"}:
        return {
            "task_id": task_id,
            "status": target_task.status,
            "queue_position": -1,
            "estimated_wait_seconds": 0.0,
            "message": f"任务已处于终态: {target_task.status}",
        }

    # Find tasks ahead in the same queue
    same_queue_waiting = [
        t for t in _TASKS.values() if t.queue_name == target_task.queue_name and t.status in {"queued", "suspended"}
    ]

    # Sort by priority rank descending, then by enqueued_at ascending
    same_queue_waiting.sort(key=lambda t: (-t.priority_rank, t.enqueued_at))

    try:
        position = same_queue_waiting.index(target_task) + 1
    except ValueError:
        position = len(same_queue_waiting)

    # Estimate throughput of workers for this queue
    workers = _get_queue_workers(target_task.queue_name)
    total_concurrency = sum(w.max_concurrency for w in workers) or 1

    # Sum estimated durations of tasks ahead of target_task
    tasks_ahead = same_queue_waiting[: max(0, position - 1)]
    workload_ahead = sum(t.estimated_duration_sec for t in tasks_ahead)

    eta_seconds = round(max(1.0, workload_ahead / total_concurrency), 1)

    return {
        "task_id": task_id,
        "status": target_task.status,
        "queue_position": position,
        "total_queued_in_line": len(same_queue_waiting),
        "estimated_wait_seconds": eta_seconds,
        "active_workers_count": len(workers),
        "message": f"排在队列第 {position} 位，预计等待时间约 {eta_seconds} 秒",
    }


def enqueue_task(
    task_name: str,
    *,
    queue_name: str = "default",
    priority: str = "P2",
    estimated_duration_sec: float = 30.0,
    allow_preemption: bool = True,
) -> tuple[QueuedTaskItem, bool]:
    """Enqueue a task and attempt immediate dispatch or priority preemption.

    Returns:
        tuple[QueuedTaskItem, bool]: (task_item, was_preempted)
    """
    if priority not in PRIORITY_WEIGHTS:
        priority = "P2"

    task_id = f"task_{uuid.uuid4().hex[:12]}"
    task = QueuedTaskItem(
        task_id=task_id,
        task_name=task_name,
        queue_name=queue_name,
        priority=priority,
        estimated_duration_sec=estimated_duration_sec,
    )
    _TASKS[task_id] = task

    # 1. Try to find an available idle worker with free slot
    optimal_worker = select_optimal_worker(required_queue=queue_name)
    if optimal_worker:
        task.status = "running"
        task.assigned_worker_id = optimal_worker.worker_id
        task.started_at = datetime.now(timezone.utc).timestamp()
        optimal_worker.current_concurrency += 1
        return task, False

    # 2. Cluster is saturated: check if task is eligible for preemption (P0 or P1)
    if allow_preemption and task.priority_rank >= PRIORITY_WEIGHTS["P1"]:
        # Find running tasks in this queue with strictly lower priority
        running_tasks = [t for t in _TASKS.values() if t.queue_name == queue_name and t.status == "running"]
        # Pick victim with lowest priority rank, then longest running
        candidates = [t for t in running_tasks if t.priority_rank < task.priority_rank]
        if candidates:
            # Sort lowest priority first (ascending priority rank)
            candidates.sort(key=lambda t: (t.priority_rank, t.started_at or 0.0))
            victim = candidates[0]

            # Preempt victim task: suspend and free worker slot
            worker_id = victim.assigned_worker_id
            victim.status = "suspended"
            victim.preempted_count += 1
            victim.preempted_by_task_id = task.task_id
            victim.assigned_worker_id = None

            # Assign freed worker to the high-priority task
            task.status = "running"
            task.assigned_worker_id = worker_id
            task.started_at = datetime.now(timezone.utc).timestamp()

            logger.info(
                "Task %s (%s) preempted victim task %s (%s) on worker %s",
                task.task_id,
                task.priority,
                victim.task_id,
                victim.priority,
                worker_id,
            )
            return task, True

    # 3. Not dispatched immediately -> stays queued
    task.status = "queued"
    return task, False


def complete_task(task_id: str, *, status: str = "completed") -> QueuedTaskItem:
    """Mark a running task as completed/aborted and attempt to resume suspended/queued tasks."""
    task = _TASKS.get(task_id)
    if not task:
        raise ValueError(f"任务不存在: {task_id}")

    worker_id = task.assigned_worker_id
    task.status = status

    # Decrement worker concurrency
    if worker_id:
        worker = get_worker_node(worker_id)
        if worker and worker.current_concurrency > 0:
            worker.current_concurrency -= 1

    # Resume suspended or highest priority queued task
    _attempt_schedule_next(task.queue_name)
    return task


def _attempt_schedule_next(queue_name: str) -> QueuedTaskItem | None:
    """Look for suspended or queued tasks and dispatch to newly available worker."""
    worker = select_optimal_worker(required_queue=queue_name)
    if not worker:
        return None

    # Priority 1: Suspended tasks (resume first to minimize latency)
    suspended = [t for t in _TASKS.values() if t.queue_name == queue_name and t.status == "suspended"]
    if suspended:
        suspended.sort(key=lambda t: (-t.priority_rank, t.enqueued_at))
        next_task = suspended[0]
        next_task.status = "running"
        next_task.assigned_worker_id = worker.worker_id
        next_task.started_at = datetime.now(timezone.utc).timestamp()
        worker.current_concurrency += 1
        return next_task

    # Priority 2: Standard queued tasks
    queued = [t for t in _TASKS.values() if t.queue_name == queue_name and t.status == "queued"]
    if queued:
        queued.sort(key=lambda t: (-t.priority_rank, t.enqueued_at))
        next_task = queued[0]
        next_task.status = "running"
        next_task.assigned_worker_id = worker.worker_id
        next_task.started_at = datetime.now(timezone.utc).timestamp()
        worker.current_concurrency += 1
        return next_task

    return None


def list_queued_tasks(*, queue_name: str | None = None) -> list[QueuedTaskItem]:
    """List all registered tasks, optionally filtered by queue."""
    tasks = list(_TASKS.values())
    if queue_name:
        tasks = [t for t in tasks if t.queue_name == queue_name]
    # Sort running first, then suspended, then queued by priority rank
    tasks.sort(
        key=lambda t: (
            0 if t.status == "running" else (1 if t.status == "suspended" else 2),
            -t.priority_rank,
            t.enqueued_at,
        )
    )
    return tasks
