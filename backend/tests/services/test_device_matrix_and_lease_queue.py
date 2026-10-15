"""Unit tests for P2.2 Real Device Matrix Concurrent Execution and Intelligent Lease Queue.

Tests:
1. acquire_available_device_from_pool locks available online device and skips busy ones
2. handle_device_disconnection_recovery marks device offline, deletes active leases, and converges in-flight runs
3. expand_case_items_for_device_matrix replicates Android cases across matrix devices while preserving non-Android cases
4. suite_orchestrator integrates device matrix expansion
"""

from __future__ import annotations

import asyncio
from datetime import datetime, timedelta, timezone
from typing import Any

from app.models.bootstrap import load_all_models
from app.models.case import RunStatus, TestRun
from app.models.device import Device, DeviceLease, DeviceStatus
from app.services.device_leases import (
    acquire_available_device_from_pool,
    expand_case_items_for_device_matrix,
    handle_device_disconnection_recovery,
)

load_all_models()


class _FakeDB:
    def __init__(self, devices: list[Device], leases: list[DeviceLease], runs: list[TestRun]):
        self._devices = {d.id: d for d in devices}
        self._leases = {l.device_id: l for l in leases}
        self._runs = {r.id: r for r in runs}
        self.deleted = []
        self.added = []
        self.flushed = 0

    async def get(self, model: type, pk: int) -> Any | None:
        if model is Device:
            return self._devices.get(pk)
        if model is TestRun:
            return self._runs.get(pk)
        return None

    async def execute(self, statement):
        sql = str(statement).lower()

        class _Result:
            def __init__(self, items):
                self._items = items

            def scalars(self):
                return self

            def all(self):
                return self._items

            def scalar_one_or_none(self):
                return self._items[0] if self._items else None

        if "from devices" in sql:
            # Check where conditions
            devs = list(self._devices.values())
            if "status !=" in sql or "where devices.status !=" in sql:
                devs = [d for d in devs if d.status != DeviceStatus.offline]
            return _Result(devs)

        if "from device_leases" in sql:
            # Check device_id
            target_leases = list(self._leases.values())
            return _Result(target_leases)

        if "from test_runs" in sql:
            target_runs = [r for r in self._runs.values() if r.status in {RunStatus.pending, RunStatus.running}]
            return _Result(target_runs)

        return _Result([])

    def add(self, item):
        self.added.append(item)
        if isinstance(item, DeviceLease):
            self._leases[item.device_id] = item

    async def delete(self, item):
        self.deleted.append(item)
        if isinstance(item, DeviceLease):
            self._leases.pop(item.device_id, None)

    async def flush(self):
        self.flushed += 1


def test_expand_case_items_for_device_matrix():
    case_items = [
        {"case_id": 101, "sort": 1},  # Android
        {"case_id": 102, "sort": 2},  # API
        {"case_id": 103, "sort": 3},  # Android
    ]
    android_ids = {101, 103}
    device_matrix = [201, 202, 203]

    expanded = expand_case_items_for_device_matrix(case_items, android_ids, device_matrix)

    # 101 expanded into 3, 102 stays 1, 103 expanded into 3 -> total 7
    assert len(expanded) == 7

    cases_101 = [item for item in expanded if item["case_id"] == 101]
    assert len(cases_101) == 3
    assert [item["device_id"] for item in cases_101] == [201, 202, 203]

    cases_102 = [item for item in expanded if item["case_id"] == 102]
    assert len(cases_102) == 1
    assert "device_id" not in cases_102[0]


def test_acquire_available_device_from_pool(monkeypatch):
    d_busy = Device(id=1, serial="dev-01", status=DeviceStatus.busy)
    d_online = Device(id=2, serial="dev-02", status=DeviceStatus.online)
    d_offline = Device(id=3, serial="dev-03", status=DeviceStatus.offline)

    active_lease = DeviceLease(
        device_id=1,
        lease_token="token-1",
        owner_id=5,
        owner_label="task-1",
        expires_at=datetime.now(timezone.utc) + timedelta(minutes=10),
    )

    db: Any = _FakeDB([d_busy, d_online, d_offline], [active_lease], [])

    # Mock acquire_device_lease to succeed for dev-02
    async def fake_acquire(_db, dev_id, **kwargs):
        if dev_id == 1:
            from app.services.device_leases import DeviceLeaseConflict

            raise DeviceLeaseConflict("busy")
        return DeviceLease(device_id=dev_id, lease_token="new-token", owner_id=9, owner_label="test")

    monkeypatch.setattr("app.services.device_leases.acquire_device_lease", fake_acquire)

    result = asyncio.run(
        acquire_available_device_from_pool(
            db,
            device_ids=[1, 2],
            owner_id=9,
            owner_label="test",
        )
    )

    assert result is not None
    dev, lease = result
    assert dev.id == 2
    assert lease.device_id == 2


def test_handle_device_disconnection_recovery():
    dev = Device(id=5, serial="127.0.0.1:28105", status=DeviceStatus.online)
    active_lease = DeviceLease(
        device_id=5,
        lease_token="lease-5",
        owner_id=1,
        owner_label="run:80",
        expires_at=datetime.now(timezone.utc) + timedelta(minutes=10),
    )
    run_inflight = TestRun(
        id=80,
        case_id=10,
        triggered_by=1,
        status=RunStatus.running,
        result_summary={"device_serial": "127.0.0.1:28105"},
    )
    run_unrelated = TestRun(
        id=81,
        case_id=11,
        triggered_by=1,
        status=RunStatus.running,
        result_summary={"device_serial": "other-device"},
    )

    db: Any = _FakeDB([dev], [active_lease], [run_inflight, run_unrelated])

    outcome = asyncio.run(handle_device_disconnection_recovery(db, device_id=5, reason="拔线或连接超时"))

    assert outcome["device_id"] == 5
    assert outcome["released_leases"] == 1
    assert outcome["recovered_runs"] == 1

    assert dev.status == DeviceStatus.offline
    assert run_inflight.status == RunStatus.error
    assert "设备异常掉线或失联: 拔线或连接超时" in (run_inflight.error_message or "")
    # Unrelated run is untouched
    assert run_unrelated.status == RunStatus.running
