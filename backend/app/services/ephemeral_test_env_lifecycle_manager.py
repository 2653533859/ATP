"""临时沙箱测试环境生命周期自动化供给与快速回收器 (T1.3)。"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from enum import Enum
from typing import Any


class EphemeralEnvStatus(str, Enum):
    """临时沙箱环境生命周期状态。"""

    PROVISIONING = "PROVISIONING"
    READY = "READY"
    IN_USE = "IN_USE"
    TEARING_DOWN = "TEARING_DOWN"
    DESTROYED = "DESTROYED"


@dataclass
class EphemeralEnvironment:
    """临时测试环境对象模型。"""

    env_id: str
    env_name: str
    namespace: str
    branch_or_pr: str
    creator: str
    services: list[str]
    cpu_limit_cores: float = 2.0
    memory_limit_gib: float = 4.0
    status: EphemeralEnvStatus = EphemeralEnvStatus.PROVISIONING
    ttl_seconds: int = 3600
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    expires_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    destroyed_at: datetime | None = None
    teardown_summary: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        now = datetime.now(timezone.utc)
        is_expired = now > self.expires_at and self.status != EphemeralEnvStatus.DESTROYED
        remaining_ttl = max(0, int((self.expires_at - now).total_seconds())) if not is_expired else 0
        return {
            "env_id": self.env_id,
            "env_name": self.env_name,
            "namespace": self.namespace,
            "branch_or_pr": self.branch_or_pr,
            "creator": self.creator,
            "services": self.services,
            "cpu_limit_cores": self.cpu_limit_cores,
            "memory_limit_gib": self.memory_limit_gib,
            "status": self.status.value,
            "ttl_seconds": self.ttl_seconds,
            "remaining_ttl_seconds": remaining_ttl,
            "is_expired": is_expired,
            "created_at": self.created_at.isoformat(),
            "expires_at": self.expires_at.isoformat(),
            "destroyed_at": self.destroyed_at.isoformat() if self.destroyed_at else None,
            "teardown_summary": self.teardown_summary,
        }


# 全局临时环境仓库
_EPHEMERAL_ENVS: dict[str, EphemeralEnvironment] = {}


def clear_ephemeral_envs() -> None:
    """清空临时环境仓库（单测专用）。"""
    _EPHEMERAL_ENVS.clear()


def provision_ephemeral_environment(
    branch_or_pr: str,
    creator: str = "ci_system",
    services: list[str] | None = None,
    cpu_limit_cores: float = 2.0,
    memory_limit_gib: float = 4.0,
    ttl_seconds: int = 3600,
) -> EphemeralEnvironment:
    """自动化供给并拉起全新隔离沙箱测试环境。"""
    short_uid = uuid.uuid4().hex[:8]
    clean_ref = "".join(c if c.isalnum() else "-" for c in branch_or_pr.lower()).strip("-")
    clean_ref = clean_ref[:20] if clean_ref else "env"
    env_id = f"eph_{clean_ref}_{short_uid}"
    namespace = f"atp-eph-{clean_ref}-{short_uid}"
    env_name = f"沙箱测试环境 [{branch_or_pr}]"

    now = datetime.now(timezone.utc)
    expires = now + timedelta(seconds=max(60, ttl_seconds))

    active_services = services or ["auth-service", "order-service", "mock-gateway"]

    env = EphemeralEnvironment(
        env_id=env_id,
        env_name=env_name,
        namespace=namespace,
        branch_or_pr=branch_or_pr,
        creator=creator,
        services=active_services,
        cpu_limit_cores=cpu_limit_cores,
        memory_limit_gib=memory_limit_gib,
        status=EphemeralEnvStatus.READY,  # 模拟初始化就绪
        ttl_seconds=ttl_seconds,
        created_at=now,
        expires_at=expires,
    )
    _EPHEMERAL_ENVS[env_id] = env
    return env


def extend_env_lease(env_id: str, extra_seconds: int = 1800) -> EphemeralEnvironment | None:
    """心跳延长临时测试环境租约 (TTL)。"""
    env = _EPHEMERAL_ENVS.get(env_id)
    if not env or env.status == EphemeralEnvStatus.DESTROYED:
        return None

    now = datetime.now(timezone.utc)
    base_time = max(now, env.expires_at)
    env.expires_at = base_time + timedelta(seconds=extra_seconds)
    env.ttl_seconds += extra_seconds
    return env


def teardown_ephemeral_environment(env_id: str) -> dict[str, Any]:
    """优雅原子级销毁并回收临时测试环境。"""
    env = _EPHEMERAL_ENVS.get(env_id)
    if not env:
        return {"success": False, "message": f"环境 [{env_id}] 未找到"}

    if env.status == EphemeralEnvStatus.DESTROYED:
        return {"success": True, "message": f"环境 [{env_id}] 此前已完成销毁回收", "env": env.to_dict()}

    now = datetime.now(timezone.utc)
    duration_minutes = round((now - env.created_at).total_seconds() / 60.0, 1)

    summary = {
        "reclaimed_cpu_cores": env.cpu_limit_cores,
        "reclaimed_memory_gib": env.memory_limit_gib,
        "reclaimed_namespace": env.namespace,
        "reclaimed_services_count": len(env.services),
        "lifetime_minutes": duration_minutes,
        "teardown_timestamp": now.isoformat(),
    }

    env.status = EphemeralEnvStatus.DESTROYED
    env.destroyed_at = now
    env.teardown_summary = summary

    return {
        "success": True,
        "message": f"临时环境 [{env.namespace}] 已成功回收，释放 {env.cpu_limit_cores} 核 CPU 与 {env.memory_limit_gib} GiB 内存。",
        "env": env.to_dict(),
    }


def reclaim_expired_environments() -> dict[str, Any]:
    """批量扫描并回收所有超期的孤儿临时沙箱环境。"""
    now = datetime.now(timezone.utc)
    reclaimed_ids = []
    total_cpu_freed = 0.0
    total_mem_freed = 0.0

    for env_id, env in list(_EPHEMERAL_ENVS.items()):
        if env.status != EphemeralEnvStatus.DESTROYED and now > env.expires_at:
            teardown_res = teardown_ephemeral_environment(env_id)
            if teardown_res.get("success"):
                reclaimed_ids.append(env_id)
                total_cpu_freed += env.cpu_limit_cores
                total_mem_freed += env.memory_limit_gib

    return {
        "reclaimed_count": len(reclaimed_ids),
        "reclaimed_env_ids": reclaimed_ids,
        "total_cpu_freed": round(total_cpu_freed, 2),
        "total_mem_freed": round(total_mem_freed, 2),
        "scanned_at": now.isoformat(),
    }


def get_ephemeral_environment(env_id: str) -> EphemeralEnvironment | None:
    """获取单个临时测试环境详情。"""
    return _EPHEMERAL_ENVS.get(env_id)


def list_ephemeral_environments(limit: int = 50, active_only: bool = False) -> list[dict[str, Any]]:
    """获取临时环境列表。"""
    envs = list(reversed(list(_EPHEMERAL_ENVS.values())))
    if active_only:
        envs = [e for e in envs if e.status != EphemeralEnvStatus.DESTROYED]
    return [e.to_dict() for e in envs[:limit]]
