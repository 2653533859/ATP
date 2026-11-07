import asyncio
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

import pytest
from sqlalchemy.dialects import postgresql

from app.models import load_all_models
from app.models.device import DeviceStatus
from app.models.ios import IosDeviceStatus
from app.services.device_leases import acquire_device_lease, get_active_device_lease
from app.services.ios_device_leases import acquire_ios_device_lease
from app.services import device_leases, ios_device_leases

load_all_models()


class _Result:
    def __init__(self, value):
        self.value = value

    def scalar_one_or_none(self):
        return self.value


class _Savepoint:
    async def __aenter__(self):
        return self

    async def __aexit__(self, *_):
        return False


class _DB:
    def __init__(self, device):
        self.results = iter([device, None])
        self.statements = []
        self.added = []

    async def execute(self, stmt):
        self.statements.append(stmt)
        if getattr(stmt, "is_update", False):
            return SimpleNamespace(rowcount=1)
        return _Result(next(self.results))

    def add(self, value):
        self.added.append(value)

    async def flush(self):
        return None

    def begin_nested(self):
        return _Savepoint()


def _postgres_sql(stmt) -> str:
    return str(stmt.compile(dialect=postgresql.dialect()))


def test_android_lease_locks_device_row_before_checking_current_lease():
    device = SimpleNamespace(id=3, status=DeviceStatus.online)
    db = _DB(device)

    lease = asyncio.run(acquire_device_lease(db, 3, owner_id=4, owner_label="test"))

    assert "FOR UPDATE" in _postgres_sql(db.statements[0])
    assert lease.device_id == 3
    assert device.status is DeviceStatus.busy


def test_ios_lease_locks_device_row_before_checking_current_lease():
    device = SimpleNamespace(id=5, status=IosDeviceStatus.online)
    db = _DB(device)

    lease = asyncio.run(acquire_ios_device_lease(db, 5, owner_id=6, owner_label="test"))

    assert "FOR UPDATE" in _postgres_sql(db.statements[0])
    assert lease.device_id == 5
    assert device.status is IosDeviceStatus.busy


def test_android_active_lease_lookup_rejects_expired_token():
    now = datetime.now(timezone.utc)
    active = SimpleNamespace(lease_token="active", expires_at=now + timedelta(minutes=5))
    expired = SimpleNamespace(lease_token="expired", expires_at=now - timedelta(seconds=1))

    active_db = _LifecycleDB([active])
    assert asyncio.run(get_active_device_lease(active_db, 3, "active")) is active

    expired_db = _LifecycleDB([expired])
    assert asyncio.run(get_active_device_lease(expired_db, 3, "expired")) is None


class _LifecycleDB:
    def __init__(self, results, device=None, expired=None, delete_rowcount=1):
        self.results = iter(results)
        self.device = device
        self.expired = expired or []
        self.deleted = []
        self.added = []
        self.flushes = 0
        self.conditional_deletes = 0
        self.delete_rowcount = delete_rowcount

    def expunge(self, _value):
        return None

    def begin_nested(self):
        return _Savepoint()

    async def execute(self, statement):
        if getattr(statement, "is_update", False):
            return SimpleNamespace(rowcount=1)
        if getattr(statement, "is_delete", False):
            self.conditional_deletes += 1
            return SimpleNamespace(rowcount=self.delete_rowcount)
        value = next(self.results)
        if isinstance(value, list):
            return SimpleNamespace(scalars=lambda: SimpleNamespace(all=lambda: value))
        return _Result(value)

    def add(self, value):
        self.added.append(value)

    async def delete(self, value):
        self.deleted.append(value)

    async def get(self, _model, _key):
        return self.device

    async def flush(self):
        self.flushes += 1


@pytest.mark.parametrize(
    ("service", "status", "device_id"),
    [
        (device_leases, DeviceStatus, 3),
        (ios_device_leases, IosDeviceStatus, 5),
    ],
)
def test_lease_lifecycle_heartbeats_releases_and_reclaims(service, status, device_id):
    prefix = "ios_" if service is ios_device_leases else ""
    acquire = getattr(service, f"acquire_{prefix}device_lease")
    heartbeat = getattr(service, f"heartbeat_{prefix}device_lease")
    release = getattr(service, f"release_{prefix}device_lease")
    reclaim = getattr(service, f"reclaim_expired_{prefix}device_leases")
    device = SimpleNamespace(id=device_id, status=status.online)
    now = datetime.now(timezone.utc)
    expired_lease = SimpleNamespace(id=9, lease_token="old", expires_at=now - timedelta(seconds=1))
    acquire_db = _LifecycleDB([device, expired_lease], device=device)
    lease = asyncio.run(acquire(acquire_db, device_id, owner_id=1, owner_label="test", ttl_seconds=30))
    # Android 用条件删除防止 SQLite 复用 id 时误删新租约；iOS 仍是 ORM 删除。
    assert acquire_db.conditional_deletes == 1 if service is device_leases else acquire_db.deleted == [expired_lease]
    assert device.status is status.busy
    assert lease.expires_at > now

    heartbeat_db = _LifecycleDB([lease], device=device)
    refreshed = asyncio.run(heartbeat(heartbeat_db, device_id, lease.lease_token, ttl_seconds=60))
    assert refreshed.expires_at > lease.heartbeat_at

    release_db = _LifecycleDB([lease], device=device)
    assert asyncio.run(release(release_db, device_id, lease.lease_token)) is True
    assert device.status is status.online
    # Android 的 release 是一条按令牌的 DELETE，iOS 仍是先读再 ORM 删除。
    assert release_db.conditional_deletes == 1 if service is device_leases else release_db.deleted == [lease]

    missing_db = _LifecycleDB([None], device=device, delete_rowcount=0)
    assert asyncio.run(release(missing_db, device_id, "missing")) is False

    device.status = status.busy
    reclaimable = SimpleNamespace(id=9, device_id=device_id, lease_token="old")
    reclaim_db = _LifecycleDB([[reclaimable]], device=device)
    assert asyncio.run(reclaim(reclaim_db)) == 1
    assert device.status is status.online


@pytest.mark.parametrize(
    ("service", "status", "device_id"),
    [(device_leases, DeviceStatus, 3), (ios_device_leases, IosDeviceStatus, 5)],
)
def test_lease_service_rejects_missing_offline_active_and_expired(service, status, device_id):
    prefix = "ios_" if service is ios_device_leases else ""
    acquire = getattr(service, f"acquire_{prefix}device_lease")
    heartbeat = getattr(service, f"heartbeat_{prefix}device_lease")
    conflict = getattr(service, "IosDeviceLeaseConflict", None) or getattr(service, "DeviceLeaseConflict")
    missing_db = _LifecycleDB([None])
    with pytest.raises(LookupError):
        asyncio.run(acquire(missing_db, device_id, owner_id=None, owner_label="test"))

    offline = SimpleNamespace(id=device_id, status=status.offline)
    with pytest.raises(conflict):
        asyncio.run(acquire(_LifecycleDB([offline]), device_id, owner_id=None, owner_label="test"))

    current = SimpleNamespace(expires_at=datetime.now(timezone.utc) + timedelta(minutes=5))
    with pytest.raises(conflict):
        asyncio.run(
            acquire(
                _LifecycleDB([SimpleNamespace(id=device_id, status=status.online), current]),
                device_id,
                owner_id=None,
                owner_label="test",
            )
        )

    expired = SimpleNamespace(expires_at=datetime.now(timezone.utc) - timedelta(seconds=1))
    with pytest.raises(conflict):
        asyncio.run(heartbeat(_LifecycleDB([expired]), device_id, "expired"))
