"""Worker Node Disconnection Detection, Heartbeat Timeout & Task Failover Service (C1.3).

Provides:
1. Automated dead worker detection based on heartbeat expiration window.
2. Orphan task reaper: extracting running tasks stranded on deceased worker nodes.
3. Atomic task failover, re-queuing, and automatic retry rescheduling to healthy nodes.
4. Permanent failure escalation when maximum failover retry attempts are exceeded.
5. Failover event auditing and diagnostic reporting.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
import logging
from typing import Any
import uuid

from app.services.adaptive_queue_preemptor import (
    _TASKS,
    _attempt_schedule_next,
    QueuedTaskItem,
)
from app.services.cluster_load_balancer import (
    _CLUSTER_NODES,
    DEFAULT_MAX_HEARTBEAT_AGE_SEC,
    ClusterWorkerNode,
    get_worker_node,
)

logger = logging.getLogger(__name__)

DEFAULT_MAX_FAILOVER_RETRIES = 3


@dataclass
class FailoverSummaryReport:
    report_id: str
    triggered_at: str
    dead_worker_id: str
    orphaned_tasks_count: int
    recovered_tasks_count: int
    permanently_failed_count: int
    recovered_task_ids: list[str] = field(default_factory=list)
    diagnostic_message: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "report_id": self.report_id,
            "triggered_at": self.triggered_at,
            "dead_worker_id": self.dead_worker_id,
            "orphaned_tasks_count": self.orphaned_tasks_count,
            "recovered_tasks_count": self.recovered_tasks_count,
            "permanently_failed_count": self.permanently_failed_count,
            "recovered_task_ids": self.recovered_task_ids,
            "diagnostic_message": self.diagnostic_message,
        }


# In-memory history of failover recovery events
_FAILOVER_HISTORY: list[FailoverSummaryReport] = []


def detect_dead_workers(
    *,
    timeout_seconds: float = DEFAULT_MAX_HEARTBEAT_AGE_SEC,
) -> list[ClusterWorkerNode]:
    """Scan cluster nodes and return workers whose heartbeat exceeded timeout window."""
    now_ts = datetime.now(timezone.utc).timestamp()
    dead: list[ClusterWorkerNode] = []
    for node in _CLUSTER_NODES.values():
        age = now_ts - node.heartbeat_timestamp
        if age > timeout_seconds and node.status != "offline":
            node.status = "offline"
            node.current_concurrency = 0
            dead.append(node)
    return dead


def failover_worker_tasks(
    dead_worker_id: str,
    *,
    max_retries: int = DEFAULT_MAX_FAILOVER_RETRIES,
) -> FailoverSummaryReport:
    """Rescue orphan running tasks stranded on dead_worker_id and atomically reschedule them."""
    now_iso = datetime.now(timezone.utc).isoformat()
    report_id = f"failover_{uuid.uuid4().hex[:12]}"

    # Mark dead worker as offline to prevent rescheduling onto it
    dead_node = get_worker_node(dead_worker_id)
    if dead_node:
        dead_node.status = "offline"
        dead_node.current_concurrency = 0

    orphans: list[QueuedTaskItem] = [
        t for t in _TASKS.values() if t.assigned_worker_id == dead_worker_id and t.status == "running"
    ]

    recovered_ids: list[str] = []
    permanently_failed = 0

    for task in orphans:
        if task.retry_count < max_retries:
            task.retry_count += 1
            task.last_failed_worker_id = dead_worker_id
            task.assigned_worker_id = None
            task.status = "queued"
            recovered_ids.append(task.task_id)

            logger.warning(
                "Task %s stranded on dead worker %s recovered (retry attempt %s/%s)",
                task.task_id,
                dead_worker_id,
                task.retry_count,
                max_retries,
            )

            # Attempt to reschedule immediately on another alive worker
            _attempt_schedule_next(task.queue_name)
        else:
            task.status = "aborted"
            task.assigned_worker_id = None
            permanently_failed += 1
            logger.error(
                "Task %s exceeded maximum failover retries (%s), marked as aborted",
                task.task_id,
                max_retries,
            )

    report = FailoverSummaryReport(
        report_id=report_id,
        triggered_at=now_iso,
        dead_worker_id=dead_worker_id,
        orphaned_tasks_count=len(orphans),
        recovered_tasks_count=len(recovered_ids),
        permanently_failed_count=permanently_failed,
        recovered_task_ids=recovered_ids,
        diagnostic_message=f"已成功对失联节点 {dead_worker_id} 执行故障转移: 救援 {len(recovered_ids)} 个孤儿任务并自动重调度入队，{permanently_failed} 个超限任务标记终止。",
    )

    _FAILOVER_HISTORY.append(report)
    return report


def scan_and_recover_dead_workers(
    *,
    timeout_seconds: float = DEFAULT_MAX_HEARTBEAT_AGE_SEC,
    max_retries: int = DEFAULT_MAX_FAILOVER_RETRIES,
) -> list[FailoverSummaryReport]:
    """Execute sweeping scan across cluster to detect dead nodes and trigger failover."""
    dead_nodes = detect_dead_workers(timeout_seconds=timeout_seconds)
    reports: list[FailoverSummaryReport] = []
    for node in dead_nodes:
        rep = failover_worker_tasks(node.worker_id, max_retries=max_retries)
        reports.append(rep)
    return reports


def list_failover_history() -> list[FailoverSummaryReport]:
    """Retrieve full history of failover recovery events."""
    return list(_FAILOVER_HISTORY)
