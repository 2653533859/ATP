"""Unit tests for multi-node Android Worker resolution, routing, and phase-1 guards."""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest
from fastapi import HTTPException
from sqlalchemy import create_engine
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.orm import Session

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from app.models.base import Base
from app.models.bootstrap import load_all_models
from app.models.device import Device, DeviceStatus
from app.services.device_resolution import DeviceResolutionError, resolve_device_async
from app.services.execution_routing import resolve_android_device_queue

load_all_models()


def test_resolve_device_async_handles_id_ambiguity_and_unclaimed():
    async def run():
        engine = create_async_engine("sqlite+aiosqlite:///:memory:")
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        maker = async_sessionmaker(engine, expire_on_commit=False)
        async with maker() as db:
            d_a = Device(serial="emulator-5554", worker_id="win-a", status=DeviceStatus.online)
            d_b = Device(serial="emulator-5554", worker_id="win-b", status=DeviceStatus.online)
            d_unclaimed = Device(serial="legacy-001", worker_id=None, status=DeviceStatus.online)
            db.add_all([d_a, d_b, d_unclaimed])
            await db.commit()

            by_id = await resolve_device_async(db, device_id=d_b.id, require_claimed=True)
            assert by_id.id == d_b.id
            assert by_id.worker_id == "win-b"

            with pytest.raises(DeviceResolutionError) as exc_ambig:
                await resolve_device_async(db, serial="emulator-5554")
            assert exc_ambig.value.code == "device_serial_ambiguous"

            with pytest.raises(DeviceResolutionError) as exc_unclaimed:
                await resolve_device_async(db, serial="legacy-001", require_claimed=True)
            assert exc_unclaimed.value.code == "device_unclaimed"

            with pytest.raises(DeviceResolutionError) as exc_mismatch:
                await resolve_device_async(db, device_id=d_a.id, serial="other-serial")
            assert exc_mismatch.value.code == "device_identity_mismatch"
        await engine.dispose()

    asyncio.run(run())


def test_resolve_android_device_queue_routes_or_rejects_offline(monkeypatch):
    from app.core import config as config_module
    from app.services import android_worker_registry

    monkeypatch.setattr(config_module.settings, "ANDROID_MULTI_NODE_ENABLED", True)
    monkeypatch.setattr(config_module.settings, "ATP_LOCAL_MODE", False)

    async def run():
        engine = create_async_engine("sqlite+aiosqlite:///:memory:")
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        maker = async_sessionmaker(engine, expire_on_commit=False)
        async with maker() as db:
            d_a = Device(serial="dev-1", worker_id="win-a", status=DeviceStatus.online)
            d_b = Device(serial="dev-2", worker_id="win-b", status=DeviceStatus.online)
            db.add_all([d_a, d_b])
            await db.commit()

            async def fake_get_worker(wid: str):
                return {"worker_id": wid, "instance_generation": 10} if wid == "win-a" else None

            monkeypatch.setattr(android_worker_registry, "get_android_worker", fake_get_worker)

            queue = await resolve_android_device_queue(db, device_id=d_a.id)
            assert queue == "android.win-a"

            with pytest.raises(DeviceResolutionError) as exc_off:
                await resolve_android_device_queue(db, device_id=d_b.id)
            assert exc_off.value.code == "worker_offline"
        await engine.dispose()

    asyncio.run(run())


def test_device_mirror_multi_node_routing_and_timeout_unknown(monkeypatch):
    from app.api.v1 import device_mirror
    from app.services import android_worker_registry
    from app.worker import tasks_device

    monkeypatch.setattr(device_mirror.settings, "ANDROID_MULTI_NODE_ENABLED", True)

    with pytest.raises(HTTPException) as exc_unclaimed:
        asyncio.run(device_mirror._dispatch_worker_operation("tap", "S1", {"x": 1, "y": 2}, worker_id=None))
    assert exc_unclaimed.value.status_code == 409
    assert "device_unclaimed" in str(exc_unclaimed.value.detail)

    async def fake_offline(_wid: str):
        return None

    monkeypatch.setattr(android_worker_registry, "get_android_worker", fake_offline)
    with pytest.raises(HTTPException) as exc_off:
        asyncio.run(device_mirror._dispatch_worker_operation("tap", "S1", {"x": 1, "y": 2}, worker_id="win-a"))
    assert exc_off.value.status_code == 503
    assert "worker_offline" in str(exc_off.value.detail)

    dispatched: list[tuple] = []

    async def fake_online(wid: str):
        return {"worker_id": wid, "instance_generation": 42}

    class FakeTimeoutResult:
        def get(self, timeout=15):
            raise TimeoutError("timed out")

    def fake_apply_async(*, args, queue, ignore_result, expires):
        dispatched.append((args, queue, expires))
        return FakeTimeoutResult()

    monkeypatch.setattr(android_worker_registry, "get_android_worker", fake_online)
    monkeypatch.setattr(tasks_device.run_android_device_operation, "apply_async", fake_apply_async)

    with pytest.raises(HTTPException) as exc_timeout:
        asyncio.run(device_mirror._dispatch_worker_operation("tap", "S1", {"x": 1, "y": 2}, worker_id="win-a"))
    assert exc_timeout.value.status_code == 504
    assert "operation_outcome_unknown" in str(exc_timeout.value.detail)
    assert len(dispatched) == 1
    assert dispatched[0][1] == "mobile_special.win-a"
    assert dispatched[0][0][2]["expected_worker_id"] == "win-a"
    assert dispatched[0][0][2]["expected_generation"] == 42


def test_phase1_blocks_scrcpy_and_interactive_agent_in_multi_node_mode(monkeypatch):
    from app.api.v1 import android_agent
    from app.device_stream import router as stream_router

    monkeypatch.setattr(stream_router.settings, "ANDROID_MULTI_NODE_ENABLED", True)
    monkeypatch.setattr(android_agent.settings, "ANDROID_MULTI_NODE_ENABLED", True)
    monkeypatch.setattr(android_agent.settings, "ANDROID_AGENT_ENABLED", True)

    with pytest.raises(HTTPException) as exc_scrcpy:
        stream_router._require_scrcpy_allowed()
    assert exc_scrcpy.value.status_code == 409
    assert "multi_node_feature_disabled" in str(exc_scrcpy.value.detail)

    with pytest.raises(HTTPException) as exc_agent:
        android_agent._require_android_agent_interactive_allowed()
    assert exc_agent.value.status_code == 409
    assert "multi_node_feature_disabled" in str(exc_agent.value.detail)


def test_devices_scan_multi_node_aggregate_and_zero_worker_guard(monkeypatch):
    from app.api.v1 import devices
    from app.worker import tasks_device

    monkeypatch.setattr(devices.settings, "ADB_SCAN_MODE", "worker")
    monkeypatch.setattr(devices.settings, "ANDROID_MULTI_NODE_ENABLED", True)

    class FakeDB:
        async def execute(self, *_args, **_kwargs):
            return SimpleNamespace(scalars=lambda: SimpleNamespace(all=lambda: []))

    async def fake_no_workers():
        return []

    monkeypatch.setattr(devices, "list_android_workers", fake_no_workers)
    res_empty = asyncio.run(devices.scan_devices(db=FakeDB(), _=None))
    assert res_empty.status == "failed"
    assert "no_online_android_worker" in (res_empty.error or "")

    async def fake_two_workers():
        return [
            {"worker_id": "win-a", "instance_generation": 1},
            {"worker_id": "win-b", "instance_generation": 2},
        ]

    queued_calls: list[dict] = []
    saved_aggregates: list[tuple] = []

    def fake_apply_async(*, kwargs, queue, ignore_result, expires):
        queued_calls.append({"kwargs": kwargs, "queue": queue})
        return SimpleNamespace(id=f"sub-{kwargs['worker_id']}")

    async def fake_save_agg(parent_id, items):
        saved_aggregates.append((parent_id, items))

    monkeypatch.setattr(devices, "list_android_workers", fake_two_workers)
    monkeypatch.setattr(tasks_device.scan_adb_devices, "apply_async", fake_apply_async)
    monkeypatch.setattr(devices, "_save_aggregate_scan", fake_save_agg)

    res_agg = asyncio.run(devices.scan_devices(db=FakeDB(), _=None))
    assert res_agg.status == "queued"
    assert res_agg.total_workers == 2
    assert {item.worker_id for item in res_agg.items} == {"win-a", "win-b"}
    assert {c["queue"] for c in queued_calls} == {"android.win-a", "android.win-b"}
    assert len(saved_aggregates) == 1


def test_suite_orchestration_stays_on_default_queue_in_multi_node_mode(monkeypatch):
    from app.core import config as config_module
    from app.models.case import CaseType
    from app.services.execution_routing import DEFAULT_EXECUTION_QUEUE, resolve_suite_execution_queue

    monkeypatch.setattr(config_module.settings, "ANDROID_MULTI_NODE_ENABLED", True)

    class FakeDB:
        async def execute(self, *_args, **_kwargs):
            return SimpleNamespace(scalars=lambda: SimpleNamespace(all=lambda: [CaseType.android, CaseType.android]))

    suite = SimpleNamespace(case_ids=[{"case_id": 1}, {"case_id": 2}])
    queue = asyncio.run(resolve_suite_execution_queue(FakeDB(), suite))
    assert queue == DEFAULT_EXECUTION_QUEUE
