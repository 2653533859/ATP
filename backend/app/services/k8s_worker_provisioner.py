"""云原生瞬时动态 Worker 容器 Pod 调度与配额管控引擎 (D1.1).

支持在 Kubernetes / Docker 容器运行时下按需动态拉起瞬时 Worker 实例，
提供严格的 CPU / 内存资源配额限制、Pod 状态机流转与过期自动化生命周期收割。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any
import uuid
import logging

logger = logging.getLogger(__name__)

# 系统安全配额红线
MAX_CPU_CORES_PER_POD = 16.0
MAX_MEMORY_MB_PER_POD = 32768  # 32GB


class ContainerRuntime(str, Enum):
    KUBERNETES = "kubernetes"
    DOCKER = "docker"
    CONTAINERD = "containerd"


class PodStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    TERMINATED = "terminated"


@dataclass
class ResourceQuota:
    cpu_limit_cores: float = 2.0
    memory_limit_mb: int = 2048
    cpu_request_cores: float = 0.5
    memory_request_mb: int = 512

    def validate(self) -> None:
        if self.cpu_limit_cores <= 0 or self.cpu_limit_cores > MAX_CPU_CORES_PER_POD:
            raise ValueError(f"CPU 配额限制需在 (0, {MAX_CPU_CORES_PER_POD}] 核区间内")
        if self.memory_limit_mb <= 0 or self.memory_limit_mb > MAX_MEMORY_MB_PER_POD:
            raise ValueError(f"内存配额限制需在 (0, {MAX_MEMORY_MB_PER_POD}] MB 区间内")
        if self.cpu_request_cores > self.cpu_limit_cores:
            raise ValueError("CPU Request 不能大于 CPU Limit")
        if self.memory_request_mb > self.memory_limit_mb:
            raise ValueError("Memory Request 不能大于 Memory Limit")

    def to_dict(self) -> dict[str, Any]:
        return {
            "cpu_limit_cores": self.cpu_limit_cores,
            "memory_limit_mb": self.memory_limit_mb,
            "cpu_request_cores": self.cpu_request_cores,
            "memory_request_mb": self.memory_request_mb,
        }


@dataclass
class EphemeralWorkerPodInstance:
    pod_id: str
    worker_name: str
    image: str
    runtime: ContainerRuntime
    assigned_queue: str
    resource_quota: ResourceQuota
    status: PodStatus = PodStatus.PENDING
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    started_at: datetime | None = None
    terminated_at: datetime | None = None
    exit_code: int | None = None
    logs: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "pod_id": self.pod_id,
            "worker_name": self.worker_name,
            "image": self.image,
            "runtime": self.runtime.value,
            "assigned_queue": self.assigned_queue,
            "resource_quota": self.resource_quota.to_dict(),
            "status": self.status.value,
            "created_at": self.created_at.isoformat(),
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "terminated_at": self.terminated_at.isoformat() if self.terminated_at else None,
            "exit_code": self.exit_code,
            "logs_count": len(self.logs),
            "metadata": self.metadata,
        }


# 全局内存 Pod 实例注册表
_ACTIVE_WORKER_PODS: dict[str, EphemeralWorkerPodInstance] = {}


def provision_worker_pod(
    worker_name: str,
    image: str = "atp/worker-python:3.12-v1",
    assigned_queue: str = "default",
    resource_quota: ResourceQuota | None = None,
    runtime: ContainerRuntime = ContainerRuntime.KUBERNETES,
    metadata: dict[str, Any] | None = None,
) -> EphemeralWorkerPodInstance:
    """动态拉起并调度瞬时 Worker 容器 Pod 实例。"""
    quota = resource_quota or ResourceQuota()
    quota.validate()

    pod_id = f"pod_worker_{uuid.uuid4().hex[:12]}"
    now = datetime.now(timezone.utc)

    pod = EphemeralWorkerPodInstance(
        pod_id=pod_id,
        worker_name=worker_name,
        image=image,
        runtime=runtime,
        assigned_queue=assigned_queue,
        resource_quota=quota,
        status=PodStatus.RUNNING,
        created_at=now,
        started_at=now,
        metadata=metadata or {},
    )

    pod.logs.append(f"[{now.isoformat()}] Pod {pod_id} initialized on {runtime.value} runtime with image {image}")
    pod.logs.append(f"[{now.isoformat()}] Quota allocated: CPU {quota.cpu_limit_cores}C, Mem {quota.memory_limit_mb}MB")

    _ACTIVE_WORKER_PODS[pod_id] = pod
    logger.info(
        "Provisioned ephemeral worker pod pod_id=%s image=%s runtime=%s queue=%s",
        pod_id,
        image,
        runtime.value,
        assigned_queue,
    )
    return pod


def list_worker_pods(
    assigned_queue: str | None = None,
    status: PodStatus | None = None,
) -> list[EphemeralWorkerPodInstance]:
    """查询当前登记的所有 Worker Pod 实例。"""
    pods = list(_ACTIVE_WORKER_PODS.values())
    if assigned_queue:
        pods = [p for p in pods if p.assigned_queue == assigned_queue]
    if status:
        pods = [p for p in pods if p.status == status]
    return pods


def get_worker_pod(pod_id: str) -> EphemeralWorkerPodInstance | None:
    """获取指定 Pod ID 的实例详情。"""
    return _ACTIVE_WORKER_PODS.get(pod_id)


def terminate_worker_pod(
    pod_id: str,
    exit_code: int = 0,
) -> EphemeralWorkerPodInstance:
    """优雅下线并销毁指定 Worker 容器 Pod。"""
    pod = _ACTIVE_WORKER_PODS.get(pod_id)
    if not pod:
        raise ValueError(f"Worker Pod 不存在: {pod_id}")

    now = datetime.now(timezone.utc)
    pod.status = PodStatus.TERMINATED if exit_code == 0 else PodStatus.FAILED
    pod.terminated_at = now
    pod.exit_code = exit_code
    pod.logs.append(f"[{now.isoformat()}] Pod terminated with exit_code {exit_code}")

    logger.info("Terminated ephemeral worker pod pod_id=%s exit_code=%s", pod_id, exit_code)
    return pod


def append_pod_logs(pod_id: str, log_line: str) -> None:
    """向指定 Pod 追加执行日志。"""
    pod = _ACTIVE_WORKER_PODS.get(pod_id)
    if pod:
        now_str = datetime.now(timezone.utc).isoformat()
        pod.logs.append(f"[{now_str}] {log_line}")


def reap_stale_worker_pods(max_lifetime_sec: float = 3600.0) -> list[str]:
    """批量巡检并收割运行时间超出寿命上限的僵尸 Worker 容器。"""
    now = datetime.now(timezone.utc)
    reaped_ids: list[str] = []

    for pod_id, pod in list(_ACTIVE_WORKER_PODS.items()):
        if pod.status in {PodStatus.RUNNING, PodStatus.PENDING}:
            lifetime = (now - pod.created_at).total_seconds()
            if lifetime > max_lifetime_sec:
                pod.status = PodStatus.TERMINATED
                pod.terminated_at = now
                pod.exit_code = 137  # OOM / Timeout Kill
                pod.logs.append(f"[{now.isoformat()}] Force reaped due to exceeding max lifetime ({lifetime:.1f}s)")
                reaped_ids.append(pod_id)

    if reaped_ids:
        logger.warning("Reaped stale worker pods count=%s pod_ids=%s", len(reaped_ids), reaped_ids)
    return reaped_ids


def reset_worker_pods_registry() -> None:
    """仅供单元测试重置状态使用。"""
    _ACTIVE_WORKER_PODS.clear()
