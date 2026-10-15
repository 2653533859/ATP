"""Unit tests for T1.1 Unified iOS Device Asset and Online Heartbeat Management.

Tests:
1. register_or_heartbeat_ios_device registers new device and updates existing heartbeats
2. Retains busy state during heartbeat renewal
3. mark_stale_ios_devices_offline converges stale active devices to offline
4. format_unified_device formats both Android and iOS entities into unified schema
5. get_unified_device_list supports platform and status filtering
6. probe_ios_wda_health tests WDA /status probe
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from typing import Any
from unittest.mock import AsyncMock, patch

import httpx
import pytest
from app.models.bootstrap import load_all_models
from app.models.device import Device, DeviceStatus
from app.models.ios import IosDevice, IosDeviceStatus
from app.services.ios_device_manager import (
    format_unified_device,
    get_unified_device_list,
    mark_stale_ios_devices_offline,
    probe_ios_wda_health,
    register_or_heartbeat_ios_device,
)

load_all_models()
NOW = datetime.now(timezone.utc)


class _Result:
    def __init__(self, scalar=None, scalars_list=None):
        self.scalar = scalar
        self.scalars_list = scalars_list or []

    def scalar_one_or_none(self):
        return self.scalar

    def scalars(self):
        return SimpleNamespace(all=lambda: self.scalars_list)


class _FakeDB:
    def __init__(self, existing_device=None, query_list=None):
        self.existing_device = existing_device
        self.query_list = query_list or []
        self.added: list[Any] = []
        self.flushed = False

    async def execute(self, _stmt):
        return _Result(self.existing_device, self.query_list)

    def add(self, item):
        self.added.append(item)

    async def flush(self):
        self.flushed = True


@pytest.mark.asyncio
async def test_register_new_ios_device():
    db: Any = _FakeDB(existing_device=None)
    dev = await register_or_heartbeat_ios_device(
        db,
        udid="00008101-001234567890ABCD",
        name="iPhone 14 Pro",
        model="iPhone15,2",
        platform_version="17.4",
        appium_server_url="http://mac-mini.local:4723",
        wda_local_port=8100,
    )

    assert dev.udid == "00008101-001234567890ABCD"
    assert dev.name == "iPhone 14 Pro"
    assert dev.status == IosDeviceStatus.online
    assert dev.wda_local_port == 8100
    assert dev.last_seen_at is not None
    assert len(db.added) == 1
    assert db.flushed is True


@pytest.mark.asyncio
async def test_heartbeat_existing_ios_device_retains_busy():
    existing = IosDevice(
        udid="00008101-001234567890ABCD",
        name="iPhone 14 Pro",
        status=IosDeviceStatus.busy,  # Currently running tests
        last_seen_at=NOW - timedelta(seconds=60),
    )
    db: Any = _FakeDB(existing_device=existing)

    updated = await register_or_heartbeat_ios_device(
        db,
        udid="00008101-001234567890ABCD",
        platform_version="17.5",  # upgraded version
    )

    assert updated.udid == "00008101-001234567890ABCD"
    assert updated.status == IosDeviceStatus.busy  # Busy state preserved
    assert updated.platform_version == "17.5"
    assert updated.last_seen_at > NOW - timedelta(seconds=10)
    assert db.flushed is True


@pytest.mark.asyncio
async def test_mark_stale_ios_devices_offline():
    stale_dev1 = IosDevice(
        udid="stale-1",
        status=IosDeviceStatus.online,
        last_seen_at=NOW - timedelta(seconds=300),
    )
    stale_dev2 = IosDevice(
        udid="stale-2",
        status=IosDeviceStatus.busy,
        last_seen_at=NOW - timedelta(seconds=200),
    )

    db: Any = _FakeDB(query_list=[stale_dev1, stale_dev2])
    count = await mark_stale_ios_devices_offline(db, timeout_seconds=120)

    assert count == 2
    assert stale_dev1.status == IosDeviceStatus.offline
    assert stale_dev2.status == IosDeviceStatus.offline
    assert db.flushed is True


def test_format_unified_device():
    # 1. iOS Device
    ios_dev = IosDevice(
        id=1,
        udid="00008030-0011223344",
        name="Lab-iPhone-13",
        model="iPhone14,5",
        platform_version="16.6",
        status=IosDeviceStatus.online,
        appium_server_url="http://192.168.1.50:4723",
        wda_local_port=8105,
        ip_address="192.168.1.101",
        port=8105,
        last_seen_at=NOW,
    )
    ios_unified = format_unified_device(ios_dev, "ios")
    assert ios_unified["platform"] == "ios"
    assert ios_unified["brand"] == "Apple"
    assert ios_unified["identifier"] == "00008030-0011223344"
    assert ios_unified["wda_local_port"] == 8105
    assert ios_unified["status"] == "online"

    # 2. Android Device
    android_dev = Device(
        id=2,
        serial="emulator-5554",
        name="Pixel 6",
        brand="Google",
        model="Pixel 6",
        os_version="13",
        status=DeviceStatus.busy,
        ip_address="127.0.0.1",
        port=5554,
        last_seen_at=NOW,
    )
    android_unified = format_unified_device(android_dev, "android")
    assert android_unified["platform"] == "android"
    assert android_unified["brand"] == "Google"
    assert android_unified["identifier"] == "emulator-5554"
    assert android_unified["wda_local_port"] is None
    assert android_unified["status"] == "busy"


@pytest.mark.asyncio
async def test_probe_ios_wda_health():
    mock_resp = AsyncMock()
    mock_resp.status_code = 200
    mock_resp.json = lambda: {"value": {"ready": True, "state": "success"}}

    with patch("httpx.AsyncClient.get", return_value=mock_resp):
        res = await probe_ios_wda_health("http://localhost:4723")
        assert res["healthy"] is True
        assert res["ready"] is True

    # Error case
    with patch("httpx.AsyncClient.get", side_effect=httpx.ConnectTimeout("WDA timeout")):
        res_err = await probe_ios_wda_health("http://localhost:4723")
        assert res_err["healthy"] is False
        assert "WDA timeout" in res_err["error"]


@pytest.mark.asyncio
async def test_get_unified_device_list():
    android_dev = Device(
        id=1,
        serial="emulator-5554",
        name="Android Dev",
        status=DeviceStatus.online,
    )
    ios_dev = IosDevice(
        id=2,
        udid="ios-udid-123",
        name="iPhone Dev",
        status=IosDeviceStatus.online,
    )

    # Mock DB returning android then ios
    calls = 0

    class _MultiDB:
        async def execute(self, _stmt):
            nonlocal calls
            calls += 1
            if calls == 1:
                return _Result(scalars_list=[android_dev])
            return _Result(scalars_list=[ios_dev])

    db: Any = _MultiDB()
    devices = await get_unified_device_list(db, platform_filter="all")
    assert len(devices) == 2
    platforms = [d["platform"] for d in devices]
    assert "android" in platforms
    assert "ios" in platforms
