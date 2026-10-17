"""iOS 真机排他性租约调度与自动续期服务单测 (T2.1)"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
import pytest

from app.services.ios_device_heartbeat_keeper import (
    clear_heartbeat_records,
    record_ios_heartbeat,
)
from app.services.ios_lease_scheduler import (
    IosDeviceUnavailableError,
    IosLeaseConflictError,
    IosLeaseError,
    acquire_ios_lease,
    clear_ios_leases,
    get_active_lease,
    heartbeat_ios_lease,
    list_active_leases,
    release_ios_lease,
    sweep_expired_ios_leases,
)
from app.services.ios_tunnel_bridge import (
    clear_ios_tunnels,
    get_ios_tunnel,
    register_ios_tunnel,
)


@pytest.fixture(autouse=True)
def clean_state():
    clear_ios_tunnels()
    clear_heartbeat_records()
    clear_ios_leases()
    yield
    clear_ios_tunnels()
    clear_heartbeat_records()
    clear_ios_leases()


def test_acquire_and_release_exclusive_lease():
    udid = "00008101-LEASE-TEST-01"
    register_ios_tunnel(
        udid=udid,
        device_name="iPhone 15 Pro",
        model="iPhone16,1",
        ios_version="17.4",
        agent_id="mac_agent_01",
        agent_name="Mac-Mini",
    )
    record_ios_heartbeat(udid=udid, agent_id="mac_agent_01", wda_alive=True)

    # 1. 成功申请排他性租约
    lease = acquire_ios_lease(
        udid=udid,
        owner_id="user_qa_101",
        owner_label="QA-Alice",
        purpose="ui_automation",
        ttl_seconds=120,
    )
    assert lease.udid == udid
    assert lease.owner_label == "QA-Alice"
    assert lease.is_active is True
    assert get_active_lease(udid) is not None
    assert len(list_active_leases()) == 1

    # 验证设备隧道状态联动为 BUSY
    tunnel = get_ios_tunnel(udid)
    assert tunnel is not None and tunnel.status == "BUSY"

    # 2. 并发冲突尝试申请被拒绝
    with pytest.raises(IosLeaseConflictError, match="正被 \\[QA-Alice\\] 独占租用中"):
        acquire_ios_lease(
            udid=udid,
            owner_id="user_dev_202",
            owner_label="Dev-Bob",
        )

    # 3. 释放租约
    res = release_ios_lease(udid=udid, lease_token=lease.lease_token)
    assert res is True
    assert get_active_lease(udid) is None
    assert len(list_active_leases()) == 0

    # 验证设备隧道状态恢复为 CONNECTED
    tunnel_post = get_ios_tunnel(udid)
    assert tunnel_post is not None and tunnel_post.status == "CONNECTED"


def test_heartbeat_and_sweep_expired_leases():
    udid = "00008101-LEASE-EXPIRY-02"
    register_ios_tunnel(
        udid=udid,
        device_name="iPhone 14",
        model="iPhone15,2",
        ios_version="16.5",
        agent_id="mac_agent_02",
        agent_name="Mac-Studio",
    )
    now = datetime.now(timezone.utc)

    lease = acquire_ios_lease(
        udid=udid,
        owner_id="worker_01",
        owner_label="Celery-Runner",
        ttl_seconds=60,
        now=now,
    )
    original_expiration = lease.expires_at

    # 续期心跳
    hb_lease = heartbeat_ios_lease(
        udid=udid,
        lease_token=lease.lease_token,
        additional_ttl_seconds=120,
        now=now + timedelta(seconds=10),
    )
    assert hb_lease.expires_at > original_expiration

    # 错误 Token 续期抛错
    with pytest.raises(IosLeaseError, match="无效的租约 Token"):
        heartbeat_ios_lease(udid=udid, lease_token="invalid_token")

    # 模拟 300 秒后过期巡检
    reclaimed = sweep_expired_ios_leases(now=now + timedelta(seconds=300))
    assert udid in reclaimed
    assert get_active_lease(udid) is None


def test_offline_device_and_force_takeover():
    udid = "00008101-OFFLINE-DEVICE-03"
    register_ios_tunnel(
        udid=udid,
        device_name="iPhone 13",
        model="iPhone14,5",
        ios_version="15.0",
        agent_id="agent_03",
        agent_name="Mac-Lab",
    )
    # 模拟设备离线
    rec = record_ios_heartbeat(udid=udid, agent_id="agent_03")
    rec.status = "OFFLINE"

    with pytest.raises(IosDeviceUnavailableError, match="处于离线状态"):
        acquire_ios_lease(udid=udid, owner_id="user_1", owner_label="User-1")

    # 恢复在线后租用并测试管理员强制接管
    rec.status = "ONLINE"
    lease_1 = acquire_ios_lease(udid=udid, owner_id="user_1", owner_label="User-1")
    assert lease_1.owner_label == "User-1"

    # 强制接管
    lease_admin = acquire_ios_lease(
        udid=udid,
        owner_id="admin_999",
        owner_label="Admin-Root",
        force_takeover=True,
    )
    assert lease_admin.owner_label == "Admin-Root"
    active_lease = get_active_lease(udid)
    assert active_lease is not None and active_lease.lease_token == lease_admin.lease_token
