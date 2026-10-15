"""Unit tests for T1.2 W3C/Appium 2 XCUITest session self-healing and lease queue.

Tests:
1. acquire_available_ios_device_from_pool skips busy/offline candidates and leases available device
2. acquire_available_ios_device_from_pool raises IosDeviceLeaseConflict when all busy
3. handle_ios_device_disconnection_recovery sets device offline, deletes lease, converges in-flight TestRun
4. is_wda_session_crash correctly identifies WDA session crashes
5. recover_wda_session successfully re-creates W3C session on Appium/WDA
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from typing import Any
from unittest.mock import AsyncMock

import pytest

from app.models.bootstrap import load_all_models
from app.models.case import RunStatus, TestRun
from app.models.ios import IosDevice, IosDeviceLease, IosDeviceStatus
from app.services.ios_device_leases import (
    IosDeviceLeaseConflict,
    acquire_available_ios_device_from_pool,
    handle_ios_device_disconnection_recovery,
)
from app.services.ios_wda_session_healer import (
    is_wda_session_crash,
    recover_wda_session,
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
    def __init__(self, devices_by_id=None, leases_by_dev_id=None, in_flight_runs=None):
        self.devices = devices_by_id or {}
        self.leases = leases_by_dev_id or {}
        self.in_flight_runs = in_flight_runs or []
        self.added: list[Any] = []
        self.deleted: list[Any] = []
        self.flushed = False

    async def get(self, model, obj_id):
        if model is IosDevice:
            return self.devices.get(obj_id)
        return None

    async def execute(self, statement):
        sql = str(statement).lower()
        compiled = getattr(statement, "compile", lambda: None)()
        params = getattr(compiled, "params", {}) or {}

        if "from ios_devices" in sql:
            dev_id = params.get("id_1") or params.get("id")
            if dev_id is not None:
                return _Result(self.devices.get(dev_id))
            return _Result(scalars_list=list(self.devices.values()))

        if "from ios_device_leases" in sql:
            dev_id = params.get("device_id_1") or params.get("device_id")
            if dev_id is not None:
                return _Result(self.leases.get(dev_id))
            return _Result(scalars_list=list(self.leases.values()))

        if "from test_runs" in sql:
            return _Result(scalars_list=self.in_flight_runs)

        return _Result(None)

    def add(self, item):
        self.added.append(item)

    async def delete(self, item):
        self.deleted.append(item)

    async def flush(self):
        self.flushed = True


@pytest.mark.asyncio
async def test_acquire_available_ios_device_from_pool():
    dev1 = IosDevice(id=1, udid="dev-busy", status=IosDeviceStatus.busy)
    lease1 = IosDeviceLease(device_id=1, expires_at=NOW + timedelta(seconds=300))

    dev2 = IosDevice(id=2, udid="dev-offline", status=IosDeviceStatus.offline)

    dev3 = IosDevice(id=3, udid="dev-avail", status=IosDeviceStatus.online)

    db: Any = _FakeDB(
        devices_by_id={1: dev1, 2: dev2, 3: dev3},
        leases_by_dev_id={1: lease1},
    )

    device, lease = await acquire_available_ios_device_from_pool(
        db,
        candidate_device_ids=[1, 2, 3],
        owner_id=99,
        owner_label="ci_runner",
    )

    assert device.id == 3
    assert device.status == IosDeviceStatus.busy
    assert lease.device_id == 3
    assert lease.owner_label == "ci_runner"
    assert db.flushed is True


@pytest.mark.asyncio
async def test_acquire_available_ios_device_all_busy_raises_conflict():
    dev1 = IosDevice(id=1, udid="dev-busy", status=IosDeviceStatus.busy)
    lease1 = IosDeviceLease(device_id=1, expires_at=NOW + timedelta(seconds=500))

    db: Any = _FakeDB(devices_by_id={1: dev1}, leases_by_dev_id={1: lease1})

    with pytest.raises(IosDeviceLeaseConflict) as exc_info:
        await acquire_available_ios_device_from_pool(db, candidate_device_ids=[1])

    assert "忙碌" in str(exc_info.value)


@pytest.mark.asyncio
async def test_handle_ios_device_disconnection_recovery():
    dev = IosDevice(id=5, udid="dev-unplugged", status=IosDeviceStatus.online)
    lease = IosDeviceLease(device_id=5, lease_token="token-5")
    run_inflight = TestRun(
        id=77,
        status=RunStatus.running.value,
        result_summary='{"device_id": 5, "platform": "ios"}',
    )
    run_unrelated = TestRun(
        id=78,
        status=RunStatus.running.value,
        result_summary='{"device_id": 99, "platform": "android"}',
    )

    db: Any = _FakeDB(
        devices_by_id={5: dev},
        leases_by_dev_id={5: lease},
        in_flight_runs=[run_inflight, run_unrelated],
    )

    res = await handle_ios_device_disconnection_recovery(db, device_id=5)

    assert res["status"] == "offline"
    assert res["released_leases"] == 1
    assert res["recovered_runs"] == 1
    assert dev.status == IosDeviceStatus.offline
    assert run_inflight.status == RunStatus.failed.value
    assert "掉线" in str(run_inflight.error_message)
    assert run_unrelated.status == RunStatus.running.value  # Unrelated run untouched


def test_is_wda_session_crash():
    assert is_wda_session_crash("A session is either terminated or not started") is True
    assert is_wda_session_crash("WebDriverAgentRunner-Runner crashed during execution") is True
    assert is_wda_session_crash("WDA unresponsive") is True
    assert is_wda_session_crash("Connection refused by inspector") is True

    # Normal application exceptions
    assert is_wda_session_crash("NoSuchElementException: unable to find element") is False
    assert is_wda_session_crash("TimeoutException: waiting for element to be visible") is False


@pytest.mark.asyncio
async def test_recover_wda_session():
    mock_status_resp = AsyncMock()
    mock_status_resp.status_code = 200

    mock_session_resp = AsyncMock()
    mock_session_resp.status_code = 200
    mock_session_resp.json = lambda: {"value": {"sessionId": "recovered-wda-session-12345"}}

    async def mock_request(_method, url, **_kwargs):
        if url.endswith("/status"):
            return mock_status_resp
        if url.endswith("/session"):
            return mock_session_resp
        return AsyncMock(status_code=404)

    mock_client = AsyncMock()
    mock_client.get = lambda url: mock_request("GET", url)
    mock_client.post = lambda url, **kw: mock_request("POST", url, **kw)

    res = await recover_wda_session(
        "http://localhost:4723",
        {"bundleId": "com.example.app"},
        http_client=mock_client,
    )

    assert res["recovered"] is True
    assert res["session_id"] == "recovered-wda-session-12345"

    # Status failure case
    mock_status_fail = AsyncMock()
    mock_status_fail.status_code = 503
    mock_client_fail = AsyncMock()
    mock_client_fail.get = AsyncMock(return_value=mock_status_fail)

    res_fail = await recover_wda_session(
        "http://localhost:4723",
        {"bundleId": "com.example.app"},
        http_client=mock_client_fail,
    )
    assert res_fail["recovered"] is False
    assert "status probe failed" in res_fail["error"]
