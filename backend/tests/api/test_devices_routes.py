import asyncio
import sys
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace

import pytest
from fastapi import HTTPException

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from app.api.v1 import devices
from app.models.device import DeviceStatus
from app.schemas.device import DeviceUpdate
from app.schemas.device_lease import DeviceLeaseAcquireIn, DeviceLeaseTokenIn


class _Result:
    def __init__(self, rows):
        self._rows = rows

    def scalars(self):
        return self

    def all(self):
        return self._rows


class _DB:
    def __init__(self, *, rows=None, objects=None):
        self.rows = list(rows or [])
        self.objects = dict(objects or {})
        self.deleted = []
        self.commits = 0
        self.refreshes = 0
        self.executed = []

    async def execute(self, query):
        self.executed.append(query)
        rows = self.rows.pop(0) if self.rows else []
        return _Result(rows)

    async def get(self, model, pk):
        return self.objects.get((model.__name__, pk))

    async def commit(self):
        self.commits += 1

    async def refresh(self, obj):
        self.refreshes += 1

    async def delete(self, obj):
        self.deleted.append(obj)


def _device(device_id=1, status=DeviceStatus.online):
    now = datetime(2026, 7, 11, tzinfo=timezone.utc)
    return SimpleNamespace(
        id=device_id,
        serial=f"serial-{device_id}",
        name="Pixel",
        model="Pixel 8",
        brand="Google",
        os_version="15",
        sdk_version="35",
        resolution="1080x2400",
        status=status,
        ip_address="127.0.0.1",
        port=5555,
        description=None,
        last_seen_at=now,
        created_at=now,
        updated_at=now,
    )


def test_list_devices_returns_ordered_query_rows():
    dev = _device()
    db = _DB(rows=[[dev]])

    result = asyncio.run(devices.list_devices(status_filter=DeviceStatus.online, db=db, _=None))

    assert result == [dev]
    assert len(db.executed) == 1


def test_scan_devices_503_when_adb_scan_fails(monkeypatch):
    async def fake_scan():
        return None

    monkeypatch.setattr(devices, "async_scan_devices", fake_scan)

    with pytest.raises(HTTPException) as exc:
        asyncio.run(devices.scan_devices(db=_DB(), _=None))

    assert exc.value.status_code == 503
    assert "ADB" in exc.value.detail


def test_scan_devices_syncs_and_returns_latest_rows(monkeypatch):
    calls = {}
    latest = _device(2)
    db = _DB(rows=[[latest]])

    async def fake_scan():
        return [{"serial": "serial-2", "status": "online"}]

    async def fake_sync(sync_db, scanned):
        calls["db"] = sync_db
        calls["scanned"] = scanned

    monkeypatch.setattr(devices, "async_scan_devices", fake_scan)
    monkeypatch.setattr(devices, "sync_devices_to_db_async", fake_sync)

    result = asyncio.run(devices.scan_devices(db=db, _=None))

    assert result == [latest]
    assert calls == {"db": db, "scanned": [{"serial": "serial-2", "status": "online"}]}
    assert db.commits == 1


def test_scan_devices_dispatches_to_worker_queue(monkeypatch):
    latest = _device(3)
    db = _DB(rows=[[latest]])
    calls = {}

    monkeypatch.setattr(devices.settings, "ADB_SCAN_MODE", "worker")
    monkeypatch.setitem(
        sys.modules,
        "app.worker.tasks_device",
        SimpleNamespace(
            scan_adb_devices=SimpleNamespace(
                apply_async=lambda **kwargs: calls.update(kwargs),
            )
        ),
    )

    result = asyncio.run(devices.scan_devices(db=db, _=None))

    assert result == [latest]
    assert calls == {"queue": "mobile_special"}
    assert db.commits == 0


def test_get_device_404_for_missing_device():
    with pytest.raises(HTTPException) as exc:
        asyncio.run(devices.get_device(device_id=404, db=_DB(), _=None))

    assert exc.value.status_code == 404


def test_update_device_applies_patch_and_refreshes():
    dev = _device()
    db = _DB(objects={("Device", 1): dev})

    result = asyncio.run(
        devices.update_device(
            device_id=1,
            body=DeviceUpdate(name="Lab phone", description="reserved", port=None),
            db=db,
            _=None,
        )
    )

    assert result is dev
    assert dev.name == "Lab phone"
    assert dev.description == "reserved"
    assert dev.port == 5555
    assert db.commits == 1 and db.refreshes == 1


def test_update_device_404_for_missing_device():
    with pytest.raises(HTTPException) as exc:
        asyncio.run(devices.update_device(device_id=404, body=DeviceUpdate(name="x"), db=_DB(), _=None))

    assert exc.value.status_code == 404


def test_delete_device_removes_existing_device():
    dev = _device()
    db = _DB(objects={("Device", 1): dev})

    asyncio.run(devices.delete_device(device_id=1, db=db, _=None))

    assert db.deleted == [dev]
    assert db.commits == 1


def test_delete_device_404_for_missing_device():
    with pytest.raises(HTTPException) as exc:
        asyncio.run(devices.delete_device(device_id=404, db=_DB(), _=None))

    assert exc.value.status_code == 404


def _lease(token="lease-token-1234567890"):
    now = datetime(2026, 7, 11, tzinfo=timezone.utc)
    return SimpleNamespace(
        device_id=1,
        owner_id=9,
        owner_label="manual",
        acquired_at=now,
        heartbeat_at=now,
        expires_at=datetime(2026, 7, 11, 0, 15, tzinfo=timezone.utc),
        lease_token=token,
    )


def test_acquire_lease_returns_token_for_owner(monkeypatch):
    lease = _lease()
    calls = {}

    async def fake_acquire(db, device_id, **kwargs):
        calls.update(db=db, device_id=device_id, kwargs=kwargs)
        return lease

    monkeypatch.setattr(devices, "acquire_device_lease", fake_acquire)
    db = _DB()
    result = asyncio.run(
        devices.acquire_lease(
            device_id=1,
            body=DeviceLeaseAcquireIn(ttl_seconds=600, owner_label="manual"),
            db=db,
            current_user=SimpleNamespace(id=9),
        )
    )

    assert result.lease_token == lease.lease_token
    assert calls == {
        "db": db,
        "device_id": 1,
        "kwargs": {"owner_id": 9, "owner_label": "manual", "ttl_seconds": 600},
    }
    assert db.commits == 1 and db.refreshes == 1


def test_heartbeat_lease_does_not_return_secret_token(monkeypatch):
    lease = _lease()

    async def fake_heartbeat(_db, _device_id, _token):
        return lease

    monkeypatch.setattr(devices, "heartbeat_device_lease", fake_heartbeat)

    result = asyncio.run(
        devices.heartbeat_lease(
            device_id=1,
            body=DeviceLeaseTokenIn(lease_token=lease.lease_token),
            db=_DB(),
            _=None,
        )
    )

    assert result.lease_token is None


def test_acquire_lease_returns_conflict_for_busy_device(monkeypatch):
    async def fake_acquire(*_args, **_kwargs):
        raise devices.DeviceLeaseConflict("busy")

    monkeypatch.setattr(devices, "acquire_device_lease", fake_acquire)

    with pytest.raises(HTTPException) as exc:
        asyncio.run(
            devices.acquire_lease(
                device_id=1,
                body=DeviceLeaseAcquireIn(),
                db=_DB(),
                current_user=SimpleNamespace(id=9),
            )
        )

    assert exc.value.status_code == 409
