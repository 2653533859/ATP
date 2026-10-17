"""iOS 真机排他性租约调度与自动续期服务 (T2.1)

解决高并发测试与多用户协作环境下的物理 iPhone 设备资源抢占与互斥问题:
1. 排他性租约申请 (Acquire Exclusive Lease):
   - 基于 UDID 与租约 Token 进行原子抢占;
   - 设备处于 OFFLINE / WDA_UNHEALTHY 时拒绝租用;
   - 设备已被占用且未超时触发 LEASE_CONFLICT;
2. 租约自动续期心跳 (Heartbeat Renewal):
   - 执行器或前端调试面板通过 token 定时刷新过期时间 (expires_at);
3. 主动释放与管理员强制回收 (Release & Force Revoke);
4. 死锁巡检与僵尸租约自动回收 (Sweep Expired Leases):
   - 防止由于 Worker 崩溃断网导致真机无限期被锁死。
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

from app.services.ios_device_heartbeat_keeper import get_heartbeat_record
from app.services.ios_tunnel_bridge import get_ios_tunnel


class IosLeaseError(Exception):
    """iOS 租约调度基础异常"""

    pass


class IosLeaseConflictError(IosLeaseError):
    """设备已被他人占用冲突"""

    def __init__(self, udid: str, current_owner: str, expires_at: str):
        super().__init__(f"设备 [{udid}] 当前正被 [{current_owner}] 独占租用中，租约预计将于 [{expires_at}] 到期")
        self.udid = udid
        self.current_owner = current_owner
        self.expires_at = expires_at


class IosDeviceUnavailableError(IosLeaseError):
    """设备离线或不可用"""

    pass


@dataclass
class IosLease:
    lease_token: str
    udid: str
    owner_id: str
    owner_label: str
    purpose: str  # automated_test | manual_debug | recording
    ttl_seconds: int
    acquired_at: str
    heartbeat_at: str
    expires_at: str
    is_active: bool = True

    def to_dict(self) -> Dict[str, Any]:
        return {
            "lease_token": self.lease_token,
            "udid": self.udid,
            "owner_id": self.owner_id,
            "owner_label": self.owner_label,
            "purpose": self.purpose,
            "ttl_seconds": self.ttl_seconds,
            "acquired_at": self.acquired_at,
            "heartbeat_at": self.heartbeat_at,
            "expires_at": self.expires_at,
            "is_active": self.is_active,
        }


# 全局轻量级活跃租约表 (udid -> IosLease)
_ACTIVE_IOS_LEASES: Dict[str, IosLease] = {}

# 历史租约归档记录
_LEASE_HISTORY: List[IosLease] = []


def clear_ios_leases() -> None:
    _ACTIVE_IOS_LEASES.clear()
    _LEASE_HISTORY.clear()


def list_active_leases() -> List[Dict[str, Any]]:
    return [l.to_dict() for l in _ACTIVE_IOS_LEASES.values() if l.is_active]


def get_active_lease(udid: str) -> Optional[IosLease]:
    lease = _ACTIVE_IOS_LEASES.get(udid)
    if lease and lease.is_active:
        return lease
    return None


def acquire_ios_lease(
    udid: str,
    owner_id: str | int,
    owner_label: str,
    purpose: str = "automated_test",
    ttl_seconds: int = 300,
    force_takeover: bool = False,
    now: datetime | None = None,
) -> IosLease:
    """申请独占租用一台物理 iPhone 设备

    若设备已被租用且未过期，抛出 IosLeaseConflictError；
    若传入 force_takeover=True（管理员权限），则强制收回并重新分配。
    """
    current_time = now or datetime.now(timezone.utc)
    now_iso = current_time.isoformat()
    ttl = max(30, min(1800, ttl_seconds))

    # 1. 验证设备反向隧道与心跳健康度
    hb = get_heartbeat_record(udid)
    if hb and hb.status == "OFFLINE":
        raise IosDeviceUnavailableError(f"设备 [{udid}] 处于离线状态 (OFFLINE)，无法申请租约")

    # 2. 检查既有租约是否冲突
    existing = get_active_lease(udid)
    if existing:
        # 检查是否自然过期
        try:
            exp_time = datetime.fromisoformat(existing.expires_at)
        except Exception:
            exp_time = current_time

        if current_time < exp_time and not force_takeover:
            raise IosLeaseConflictError(
                udid=udid,
                current_owner=existing.owner_label,
                expires_at=existing.expires_at,
            )
        # 若已过期或强制接管，失效旧租约
        existing.is_active = False
        _LEASE_HISTORY.append(existing)

    token = f"ios_lease_{uuid.uuid4().hex}"
    expires_time = current_time + timedelta(seconds=ttl)

    lease = IosLease(
        lease_token=token,
        udid=udid,
        owner_id=str(owner_id),
        owner_label=owner_label,
        purpose=purpose,
        ttl_seconds=ttl,
        acquired_at=now_iso,
        heartbeat_at=now_iso,
        expires_at=expires_time.isoformat(),
        is_active=True,
    )
    _ACTIVE_IOS_LEASES[udid] = lease

    # 同步设备隧道状态为 BUSY
    tunnel = get_ios_tunnel(udid)
    if tunnel:
        tunnel.status = "BUSY"

    return lease


def heartbeat_ios_lease(
    udid: str,
    lease_token: str,
    additional_ttl_seconds: int | None = None,
    now: datetime | None = None,
) -> IosLease:
    """为既有租约发送续期心跳"""
    current_time = now or datetime.now(timezone.utc)
    lease = get_active_lease(udid)

    if not lease or lease.lease_token != lease_token:
        raise IosLeaseError(f"无效的租约 Token 或设备 [{udid}] 未处于活动租用状态")

    ttl = additional_ttl_seconds or lease.ttl_seconds
    new_expires = current_time + timedelta(seconds=ttl)

    lease.heartbeat_at = current_time.isoformat()
    lease.expires_at = new_expires.isoformat()
    return lease


def release_ios_lease(
    udid: str,
    lease_token: str | None = None,
    admin_force: bool = False,
) -> bool:
    """释放并归还 iPhone 设备租约"""
    lease = get_active_lease(udid)
    if not lease:
        return False

    if not admin_force and (not lease_token or lease.lease_token != lease_token):
        raise IosLeaseError("释放租约失败: 提供的租约凭据 token 不匹配且未启用管理员强制权限")

    lease.is_active = False
    _LEASE_HISTORY.append(lease)
    del _ACTIVE_IOS_LEASES[udid]

    # 将设备隧道状态恢复为 CONNECTED
    tunnel = get_ios_tunnel(udid)
    if tunnel:
        tunnel.status = "CONNECTED"

    return True


def sweep_expired_ios_leases(now: datetime | None = None) -> List[str]:
    """巡检并自动强制回收全部超期失效的僵尸租约

    返回: 被自动回收的设备 UDID 列表
    """
    current_time = now or datetime.now(timezone.utc)
    reclaimed_udids: List[str] = []

    for udid, lease in list(_ACTIVE_IOS_LEASES.items()):
        if not lease.is_active:
            continue

        try:
            exp_time = datetime.fromisoformat(lease.expires_at)
        except Exception:
            exp_time = current_time

        if current_time >= exp_time:
            lease.is_active = False
            _LEASE_HISTORY.append(lease)
            del _ACTIVE_IOS_LEASES[udid]
            reclaimed_udids.append(udid)

            tunnel = get_ios_tunnel(udid)
            if tunnel:
                tunnel.status = "CONNECTED"

    return reclaimed_udids
