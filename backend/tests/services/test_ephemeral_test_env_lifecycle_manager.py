"""临时沙箱测试环境生命周期自动化供给与快速回收单元测试 (T1.3)。"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
import pytest
from app.services.ephemeral_test_env_lifecycle_manager import (
    EphemeralEnvStatus,
    clear_ephemeral_envs,
    extend_env_lease,
    get_ephemeral_environment,
    list_ephemeral_environments,
    provision_ephemeral_environment,
    reclaim_expired_environments,
    teardown_ephemeral_environment,
)


@pytest.fixture(autouse=True)
def _reset_env_state():
    clear_ephemeral_envs()
    yield
    clear_ephemeral_envs()


def test_provision_ephemeral_environment():
    """测试供给拉起全新沙箱环境。"""
    env = provision_ephemeral_environment(
        branch_or_pr="pr-1024-checkout",
        creator="ci_bot",
        services=["order-service", "inventory-service"],
        cpu_limit_cores=4.0,
        memory_limit_gib=8.0,
        ttl_seconds=3600,
    )

    assert env.env_id.startswith("eph_pr-1024-checkout_")
    assert env.namespace.startswith("atp-eph-pr-1024-checkout-")
    assert env.status == EphemeralEnvStatus.READY
    assert env.cpu_limit_cores == 4.0
    assert len(env.services) == 2
    assert env.to_dict()["remaining_ttl_seconds"] > 0
    assert not env.to_dict()["is_expired"]

    found = get_ephemeral_environment(env.env_id)
    assert found is not None
    assert found.env_id == env.env_id


def test_extend_env_lease():
    """测试心跳延长租约时间。"""
    env = provision_ephemeral_environment(branch_or_pr="feat-pay", ttl_seconds=600)
    old_expires = env.expires_at

    updated = extend_env_lease(env.env_id, extra_seconds=1800)
    assert updated is not None
    assert updated.expires_at > old_expires
    assert updated.ttl_seconds == 2400


def test_teardown_ephemeral_environment():
    """测试手动优雅销毁回收沙箱环境。"""
    env = provision_ephemeral_environment(branch_or_pr="bugfix-cart", cpu_limit_cores=2.0, memory_limit_gib=4.0)
    res = teardown_ephemeral_environment(env.env_id)

    assert res["success"] is True
    assert "成功回收" in res["message"]

    destroyed_env = get_ephemeral_environment(env.env_id)
    assert destroyed_env is not None
    assert destroyed_env.status == EphemeralEnvStatus.DESTROYED
    assert destroyed_env.destroyed_at is not None
    assert destroyed_env.teardown_summary["reclaimed_cpu_cores"] == 2.0
    assert destroyed_env.teardown_summary["reclaimed_memory_gib"] == 4.0


def test_reclaim_expired_environments():
    """测试自动扫描并回收超期孤儿测试环境。"""
    # 构造一个超期环境
    env = provision_ephemeral_environment(branch_or_pr="stale-branch", ttl_seconds=100)
    # 人工倒退过期时间
    env.expires_at = datetime.now(timezone.utc) - timedelta(seconds=10)

    # 构造一个正常有效环境
    valid_env = provision_ephemeral_environment(branch_or_pr="valid-branch", ttl_seconds=3600)

    res = reclaim_expired_environments()
    assert res["reclaimed_count"] == 1
    assert env.env_id in res["reclaimed_env_ids"]
    found_stale = get_ephemeral_environment(env.env_id)
    assert found_stale is not None and found_stale.status == EphemeralEnvStatus.DESTROYED
    found_valid = get_ephemeral_environment(valid_env.env_id)
    assert found_valid is not None and found_valid.status == EphemeralEnvStatus.READY


def test_list_environments_active_only():
    """测试过滤仅活跃沙箱环境。"""
    env1 = provision_ephemeral_environment(branch_or_pr="env1")
    provision_ephemeral_environment(branch_or_pr="env2")
    teardown_ephemeral_environment(env1.env_id)

    all_envs = list_ephemeral_environments(active_only=False)
    assert len(all_envs) == 2

    active_envs = list_ephemeral_environments(active_only=True)
    assert len(active_envs) == 1
    assert active_envs[0]["branch_or_pr"] == "env2"
