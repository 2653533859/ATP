"""API behavior tests for iOS/Appium assets and leases."""

import asyncio
from datetime import datetime, timezone
import plistlib
from types import SimpleNamespace
import zipfile

import pytest
from fastapi import HTTPException

from app.api.v1 import ios
from app.models.bootstrap import load_all_models
from app.models.ios import IosDeviceStatus
from app.schemas.device_lease import DeviceLeaseAcquireIn, DeviceLeaseTokenIn
from app.schemas.ios import IosDeviceCreate, IosDeviceUpdate

load_all_models()


class _Result:
    def __init__(self, rows=None, scalar=None):
        self.rows = list(rows or [])
        self.scalar = scalar

    def scalars(self):
        return self

    def all(self):
        return self.rows

    def scalar_one_or_none(self):
        return self.scalar


class _DB:
    def __init__(self, *, rows=None, scalars=None, objects=None):
        self.rows = list(rows or [])
        self.scalars = list(scalars or [])
        self.objects = dict(objects or {})
        self.added = []
        self.deleted = []
        self.commits = 0
        self.refreshes = 0

    async def execute(self, _query):
        if self.scalars:
            return _Result(scalar=self.scalars.pop(0))
        return _Result(rows=self.rows.pop(0) if self.rows else [])

    async def get(self, model, pk):
        return self.objects.get((model.__name__, pk))

    def add(self, obj):
        self.added.append(obj)

    async def commit(self):
        self.commits += 1

    async def refresh(self, _obj):
        self.refreshes += 1

    async def delete(self, obj):
        self.deleted.append(obj)


def _device(device_id=1):
    now = datetime(2026, 8, 7, tzinfo=timezone.utc)
    return SimpleNamespace(
        id=device_id,
        udid=f"udid-{device_id}",
        name="iPhone",
        model="iPhone 15",
        platform_version="17.5",
        status=IosDeviceStatus.online,
        appium_server_url="http://mac-worker:4723",
        wda_local_port=8100,
        ip_address=None,
        port=None,
        description=None,
        last_seen_at=now,
        created_at=now,
        updated_at=now,
    )


def _lease():
    now = datetime(2026, 8, 7, tzinfo=timezone.utc)
    return SimpleNamespace(
        device_id=1,
        owner_id=7,
        owner_label="ios-run:1",
        acquired_at=now,
        heartbeat_at=now,
        expires_at=now,
        lease_token="lease-token-1234567890",
    )


def test_list_ios_devices_filters_and_returns_rows():
    device = _device()
    result = asyncio.run(
        ios.list_ios_devices(status_filter=IosDeviceStatus.online, db=_DB(rows=[[device]]), _user=None)
    )
    assert result == [device]


def test_read_ipa_metadata_extracts_bundle_id_and_version(tmp_path):
    ipa = tmp_path / "karing.ipa"
    with zipfile.ZipFile(ipa, "w") as archive:
        archive.writestr(
            "Payload/Karing.app/Info.plist",
            plistlib.dumps(
                {
                    "CFBundleIdentifier": "com.example.karing",
                    "CFBundleShortVersionString": "1.2.3",
                }
            ),
        )

    assert ios._read_ipa_metadata(str(ipa)) == {
        "bundle_id": "com.example.karing",
        "version_name": "1.2.3",
    }


def test_read_ipa_metadata_is_best_effort_for_invalid_archives(tmp_path):
    invalid = tmp_path / "invalid.ipa"
    invalid.write_bytes(b"not an ipa")

    assert ios._read_ipa_metadata(str(invalid)) == {}


def test_create_ios_device_normalizes_appium_url_and_rejects_duplicate():
    db = _DB(scalars=[None])
    result = asyncio.run(
        ios.create_ios_device(
            IosDeviceCreate(udid="udid-1", appium_server_url="http://mac-worker:4723"),
            db=db,
            _user=None,
        )
    )
    assert result is db.added[0]
    assert result.appium_server_url == "http://mac-worker:4723/"
    assert db.commits == 1

    duplicate_db = _DB(scalars=[_device()])
    with pytest.raises(HTTPException) as exc:
        asyncio.run(
            ios.create_ios_device(
                IosDeviceCreate(udid="udid-1"),
                db=duplicate_db,
                _user=None,
            )
        )
    assert exc.value.status_code == 409


def test_update_ios_device_changes_status_and_server():
    device = _device()
    db = _DB(objects={("IosDevice", 1): device})
    result = asyncio.run(
        ios.update_ios_device(
            1,
            IosDeviceUpdate(status=IosDeviceStatus.busy, appium_server_url="http://new-worker:4723"),
            db=db,
            _user=None,
        )
    )
    assert result is device
    assert device.status is IosDeviceStatus.busy
    assert device.appium_server_url == "http://new-worker:4723/"
    assert db.commits == 1


def test_ios_lease_api_returns_token_only_on_acquire(monkeypatch):
    lease = _lease()

    async def fake_acquire(db, device_id, **kwargs):
        assert device_id == 1
        assert kwargs["owner_id"] == 7
        return lease

    async def fake_heartbeat(*_args, **_kwargs):
        return lease

    monkeypatch.setattr(ios, "acquire_ios_device_lease", fake_acquire)
    monkeypatch.setattr(ios, "heartbeat_ios_device_lease", fake_heartbeat)
    db = _DB()
    acquired = asyncio.run(ios.acquire_ios_lease(1, DeviceLeaseAcquireIn(), db=db, current_user=SimpleNamespace(id=7)))
    assert acquired.lease_token == lease.lease_token
    refreshed = asyncio.run(
        ios.heartbeat_ios_lease(1, DeviceLeaseTokenIn(lease_token=lease.lease_token), db=_DB(), _user=None)
    )
    assert refreshed.lease_token is None
