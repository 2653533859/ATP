"""Cluster Worker Node Dynamic Load Monitoring & Capacity Scoring Service (C1.1).

Provides:
1. Cross-node worker heartbeat registration and real-time metric tracking (CPU, Memory, Concurrency).
2. Multi-metric weighted load scoring and available capacity index calculation.
3. Optimal worker node selection for adaptive task dispatching.
4. Cluster-wide concurrency waterline and capacity utilization analytics.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
import logging
from typing import Any

logger = logging.getLogger(__name__)

DEFAULT_MAX_HEARTBEAT_AGE_SEC = 30.0


@dataclass
class ClusterWorkerNode:
    worker_id: str
    hostname: str
    ip_address: str
    queues: list[str] = field(default_factory=lambda: ["default"])
    status: str = "online"  # "online" | "busy" | "draining" | "offline"
    current_concurrency: int = 0
    max_concurrency: int = 10
    cpu_usage_pct: float = 0.0
    memory_usage_pct: float = 0.0
    heartbeat_timestamp: float = field(default_factory=lambda: datetime.now(timezone.utc).timestamp())
    weight: float = 1.0

    @property
    def is_alive(self) -> bool:
        """Check if worker heartbeat is fresh within max acceptable age."""
        now = datetime.now(timezone.utc).timestamp()
        return (now - self.heartbeat_timestamp) <= DEFAULT_MAX_HEARTBEAT_AGE_SEC

    @property
    def concurrency_ratio_pct(self) -> float:
        """Percentage of concurrency capacity currently consumed."""
        if self.max_concurrency <= 0:
            return 100.0
        return min(100.0, (self.current_concurrency / self.max_concurrency) * 100.0)

    def calculate_load_score(self) -> float:
        """Calculate composite weighted load score (0.0 to 100.0, higher means heavier load).

        Weights:
        - 50% Concurrency load
        - 30% CPU load
        - 20% Memory load
        """
        base_load = (
            0.50 * self.concurrency_ratio_pct
            + 0.30 * min(100.0, max(0.0, self.cpu_usage_pct))
            + 0.20 * min(100.0, max(0.0, self.memory_usage_pct))
        )
        if self.current_concurrency >= self.max_concurrency:
            base_load = max(100.0, base_load + 20.0)
        return round(min(150.0, base_load), 2)

    def calculate_capacity_score(self) -> float:
        """Calculate available capacity score (0.0 to 100.0, higher means more available capacity)."""
        load = self.calculate_load_score()
        available = max(0.0, 100.0 - load)
        return round(available * max(0.1, self.weight), 2)

    @property
    def capacity_level(self) -> str:
        """Classify health / capacity state into standardized operational tier."""
        if not self.is_alive or self.status == "offline":
            return "OFFLINE"
        if self.status == "draining":
            return "DRAINING"
        cap = self.calculate_capacity_score()
        if cap >= 70.0:
            return "HEALTHY_IDLE"
        if cap >= 40.0:
            return "MODERATE_LOAD"
        if cap > 0.0:
            return "HEAVY_LOAD"
        return "OVERLOADED"

    def to_dict(self) -> dict[str, Any]:
        return {
            "worker_id": self.worker_id,
            "hostname": self.hostname,
            "ip_address": self.ip_address,
            "queues": self.queues,
            "status": self.status,
            "current_concurrency": self.current_concurrency,
            "max_concurrency": self.max_concurrency,
            "cpu_usage_pct": round(self.cpu_usage_pct, 1),
            "memory_usage_pct": round(self.memory_usage_pct, 1),
            "heartbeat_timestamp": self.heartbeat_timestamp,
            "is_alive": self.is_alive,
            "load_score": self.calculate_load_score(),
            "capacity_score": self.calculate_capacity_score(),
            "capacity_level": self.capacity_level,
            "weight": self.weight,
        }


# In-memory registry of cluster worker nodes
_CLUSTER_NODES: dict[str, ClusterWorkerNode] = {}


def register_worker_heartbeat(
    worker_id: str,
    hostname: str,
    ip_address: str,
    *,
    queues: list[str] | None = None,
    current_concurrency: int = 0,
    max_concurrency: int = 10,
    cpu_usage_pct: float = 0.0,
    memory_usage_pct: float = 0.0,
    weight: float = 1.0,
    status: str = "online",
) -> ClusterWorkerNode:
    """Register or refresh heartbeat and metrics of a cluster worker node."""
    now_ts = datetime.now(timezone.utc).timestamp()
    node = _CLUSTER_NODES.get(worker_id)
    if node is None:
        node = ClusterWorkerNode(
            worker_id=worker_id,
            hostname=hostname,
            ip_address=ip_address,
            queues=queues or ["default"],
            status=status,
            current_concurrency=current_concurrency,
            max_concurrency=max_concurrency,
            cpu_usage_pct=cpu_usage_pct,
            memory_usage_pct=memory_usage_pct,
            heartbeat_timestamp=now_ts,
            weight=weight,
        )
        _CLUSTER_NODES[worker_id] = node
    else:
        node.hostname = hostname
        node.ip_address = ip_address
        if queues is not None:
            node.queues = queues
        node.status = status
        node.current_concurrency = current_concurrency
        node.max_concurrency = max_concurrency
        node.cpu_usage_pct = cpu_usage_pct
        node.memory_usage_pct = memory_usage_pct
        node.heartbeat_timestamp = now_ts
        node.weight = weight

    return node


def get_worker_node(worker_id: str) -> ClusterWorkerNode | None:
    """Retrieve a worker node by its ID."""
    return _CLUSTER_NODES.get(worker_id)


def list_cluster_nodes(
    *,
    queue: str | None = None,
    only_alive: bool = True,
) -> list[ClusterWorkerNode]:
    """List cluster worker nodes with optional queue filter and freshness check."""
    nodes = list(_CLUSTER_NODES.values())
    filtered: list[ClusterWorkerNode] = []
    for n in nodes:
        if only_alive and not n.is_alive:
            continue
        if queue and queue not in n.queues and "*" not in n.queues:
            continue
        filtered.append(n)
    return filtered


def select_optimal_worker(
    *,
    required_queue: str = "default",
    exclude_worker_ids: list[str] | None = None,
) -> ClusterWorkerNode | None:
    """Select the optimal worker node with maximum available capacity for task dispatching.

    Pre-requisites:
    - Must be online & alive (fresh heartbeat)
    - Not in exclude_worker_ids
    - Subscribes to required_queue
    - Has available concurrency slot (current < max)
    """
    excluded = set(exclude_worker_ids or [])
    candidates = list_cluster_nodes(queue=required_queue, only_alive=True)

    eligible: list[ClusterWorkerNode] = []
    for n in candidates:
        if n.worker_id in excluded:
            continue
        if n.status != "online":
            continue
        if n.current_concurrency >= n.max_concurrency:
            continue
        eligible.append(n)

    if not eligible:
        return None

    # Pick node with maximum available capacity score
    return max(eligible, key=lambda node: (node.calculate_capacity_score(), -node.current_concurrency))


def get_cluster_capacity_overview() -> dict[str, Any]:
    """Calculate cluster-wide capacity utilization, total concurrency, and health distribution."""
    all_nodes = list(_CLUSTER_NODES.values())
    alive_nodes = [n for n in all_nodes if n.is_alive]

    total_concurrency_slots = sum(n.max_concurrency for n in alive_nodes)
    total_active_tasks = sum(n.current_concurrency for n in alive_nodes)
    cluster_utilization_pct = (
        round((total_active_tasks / total_concurrency_slots) * 100.0, 2) if total_concurrency_slots > 0 else 0.0
    )

    avg_cpu = round(sum(n.cpu_usage_pct for n in alive_nodes) / len(alive_nodes), 1) if alive_nodes else 0.0
    avg_mem = round(sum(n.memory_usage_pct for n in alive_nodes) / len(alive_nodes), 1) if alive_nodes else 0.0

    distribution = {
        "HEALTHY_IDLE": sum(1 for n in alive_nodes if n.capacity_level == "HEALTHY_IDLE"),
        "MODERATE_LOAD": sum(1 for n in alive_nodes if n.capacity_level == "MODERATE_LOAD"),
        "HEAVY_LOAD": sum(1 for n in alive_nodes if n.capacity_level == "HEAVY_LOAD"),
        "OVERLOADED": sum(1 for n in alive_nodes if n.capacity_level == "OVERLOADED"),
        "OFFLINE": len(all_nodes) - len(alive_nodes),
    }

    return {
        "total_nodes_registered": len(all_nodes),
        "total_alive_nodes": len(alive_nodes),
        "total_concurrency_slots": total_concurrency_slots,
        "total_active_tasks": total_active_tasks,
        "cluster_utilization_pct": cluster_utilization_pct,
        "average_cpu_pct": avg_cpu,
        "average_memory_pct": avg_mem,
        "health_distribution": distribution,
    }
