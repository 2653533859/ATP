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
