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
    monkeypatch.setattr(tasks_device.run_android_device_operation, "apply_async", fake_apply_async, raising=False)

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
    monkeypatch.setattr(tasks_device.scan_adb_devices, "apply_async", fake_apply_async, raising=False)
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


def test_device_id_only_lowcode_case_and_extra_vars_override(monkeypatch):
    """device_id-only cases must resolve serial into steps, and extra_vars must override case.config."""
    from app.core import config as config_module
    from app.models.case import CaseType, RunStatus, TestCase, TestRun
    from app.worker.executors import android_lowcode_executor as ale

    monkeypatch.setattr(config_module.settings, "ANDROID_MULTI_NODE_ENABLED", True)
    monkeypatch.setattr(config_module.settings, "ATP_LOCAL_MODE", False)
    monkeypatch.setattr(config_module.settings, "ANDROID_WORKER_ID", "win-b")

    executed_serials: list[str] = []

    def fake_exec_step(serial, action, params):
        executed_serials.append(serial)
        return {"success": True, "error": None}

    async def fake_precheck(*_args, **_kwargs):
        return SimpleNamespace(ok=True, items=[])

    async def fake_screenshot(*_args, **_kwargs):
        return None

    monkeypatch.setattr(ale, "_execute_step_sync", fake_exec_step)
    monkeypatch.setattr(ale, "precheck_android_execution", fake_precheck)
    monkeypatch.setattr(ale, "_take_screenshot", fake_screenshot)
    monkeypatch.setattr(ale, "publish_run_event", lambda *_a, **_k: asyncio.sleep(0))

    async def run():
        engine = create_async_engine("sqlite+aiosqlite:///:memory:")
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        maker = async_sessionmaker(engine, expire_on_commit=False)
        async with maker() as db:
            d_a = Device(serial="emu-a", worker_id="win-a", status=DeviceStatus.online)
            d_b = Device(serial="emu-b", worker_id="win-b", status=DeviceStatus.online)
            db.add_all([d_a, d_b])
            await db.commit()

            # 1) Case has ONLY device_id (no device_serial)
            case1 = TestCase(
                name="ID-only",
                case_code="TC-MN-1",
                case_type=CaseType.android,
                module_id=None,
                config={
                    "device_id": d_b.id,
                    "collect_device_artifacts": False,
                    "steps": [{"action": "click", "params": {"x": 10, "y": 20}}],
                },
            )
            run1 = TestRun(id=501, case_id=1, status=RunStatus.running)
            await ale.run_android_lowcode(db, run1, case1, {})
            assert run1.status == RunStatus.passed
            assert executed_serials == ["emu-b"]
            assert run1.result_summary["device_id"] == d_b.id

            # 2) Suite matrix overrides case.config (d_a) with extra_vars (d_b) on worker win-b
            executed_serials.clear()
            case2 = TestCase(
                name="SuiteOverride",
                case_code="TC-MN-2",
                case_type=CaseType.android,
                module_id=None,
                config={
                    "device_id": d_a.id,
                    "device_serial": "emu-a",
                    "collect_device_artifacts": False,
                    "steps": [{"action": "click", "params": {"x": 5, "y": 5}}],
                },
            )
            run2 = TestRun(id=502, case_id=2, status=RunStatus.running)
            await ale.run_android_lowcode(db, run2, case2, {"device_id": d_b.id})
            assert run2.status == RunStatus.passed
            assert executed_serials == ["emu-b"]
            assert run2.result_summary["device_id"] == d_b.id
        await engine.dispose()

    asyncio.run(run())


def test_disconnection_recovery_isolates_same_serial_across_workers():
    """Disconnecting emulator-5554 on win-a must NOT terminate an active run on win-b's emulator-5554."""
    from app.models.case import CaseType, RunStatus, TestCase, TestRun
    from app.services.device_leases import acquire_device_lease, handle_device_disconnection_recovery

    async def run():
        engine = create_async_engine("sqlite+aiosqlite:///:memory:")
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        maker = async_sessionmaker(engine, expire_on_commit=False)
        async with maker() as db:
            from app.models.project import Module, Project
            from app.models.user import User

            user = User(username="u1", email="u1@example.com", hashed_password="x")
            db.add(user)
            await db.flush()
            proj = Project(name="P1", owner_id=user.id)
            db.add(proj)
            await db.flush()
            mod = Module(name="M1", project_id=proj.id)
            db.add(mod)
            await db.flush()

            d_a = Device(serial="emulator-5554", worker_id="win-a", status=DeviceStatus.online)
            d_b = Device(serial="emulator-5554", worker_id="win-b", status=DeviceStatus.online)
            case = TestCase(
                name="AndroidCase",
                case_code="TC-MN-3",
                summary="demo",
                case_type=CaseType.android,
                module_id=mod.id,
                creator_id=user.id,
                owner_id=user.id,
                config={},
            )
            db.add_all([d_a, d_b, case])
            await db.commit()

            run_a = TestRun(
                case_id=case.id,
                triggered_by=user.id,
                status=RunStatus.running,
                result_summary={"device_serial": "emulator-5554"},
            )
            run_b = TestRun(
                case_id=case.id,
                triggered_by=user.id,
                status=RunStatus.running,
                result_summary={"device_id": d_b.id, "device_serial": "emulator-5554"},
            )
            db.add_all([run_a, run_b])
            await db.commit()

            await acquire_device_lease(
                db, d_a.id, owner_id=user.id, owner_label=f"case-run:{run_a.id}", ttl_seconds=120
            )
            await acquire_device_lease(
                db, d_b.id, owner_id=user.id, owner_label=f"case-run:{run_b.id}", ttl_seconds=120
            )
            await db.commit()

            res = await handle_device_disconnection_recovery(db, d_a.id, reason="win-a USB 断开")
            await db.commit()
            assert res["recovered_runs"] == 1
            assert run_a.status == RunStatus.error
            assert run_b.status == RunStatus.running
        await engine.dispose()

    asyncio.run(run())


def test_registry_outage_maps_to_503_and_matrix_parent_routes_to_default(monkeypatch):
    from app.core import config as config_module
    from app.models.case import CaseType
    from app.services import android_worker_registry
    from app.services.device_leases import expand_case_items_for_device_matrix
    from app.services.execution_routing import (
        DEFAULT_EXECUTION_QUEUE,
        http_status_for_device_resolution,
        resolve_android_case_dispatch_target,
    )

    monkeypatch.setattr(config_module.settings, "ANDROID_MULTI_NODE_ENABLED", True)
    monkeypatch.setattr(config_module.settings, "ATP_LOCAL_MODE", False)

    async def boom_worker(_wid: str):
        raise android_worker_registry.AndroidWorkerRegistryError("redis down")

    monkeypatch.setattr(android_worker_registry, "get_android_worker", boom_worker)

    async def run():
        engine = create_async_engine("sqlite+aiosqlite:///:memory:")
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        maker = async_sessionmaker(engine, expire_on_commit=False)
        async with maker() as db:
            d_a = Device(serial="dev-1", worker_id="win-a", status=DeviceStatus.online)
            db.add(d_a)
            await db.commit()

            single_case = SimpleNamespace(case_type=CaseType.android, config={"device_id": d_a.id})
            with pytest.raises(DeviceResolutionError) as exc_reg:
                await resolve_android_case_dispatch_target(db, single_case, {})
            assert exc_reg.value.code == "worker_registry_unavailable"
            assert http_status_for_device_resolution(exc_reg.value.code) == 503

            matrix_case = SimpleNamespace(
                case_type=CaseType.android,
                config={"device_matrix": [{"device_id": d_a.id}]},
            )
            q, meta = await resolve_android_case_dispatch_target(db, matrix_case, {})
            assert q == DEFAULT_EXECUTION_QUEUE
            assert meta == {}
        await engine.dispose()

    asyncio.run(run())

    expanded = expand_case_items_for_device_matrix(
        [{"case_id": 10}, {"case_id": 20}],
        {10},
        [1, "emu-legacy", {"serial": "emu-dict"}],
    )
    assert len(expanded) == 4
    assert expanded[0]["device_id"] == 1
    assert expanded[1]["device_serial"] == "emu-legacy"
    assert expanded[2]["device_serial"] == "emu-dict"
    assert expanded[3] == {"case_id": 20}


def test_claim_connect_scan_expiry_and_runtime_contracts(monkeypatch):
    import subprocess
    from uuid import uuid4

    from app.api.v1 import devices, runtime
    from app.core import config as config_module
    from app.models.user import User, UserRole
    from app.schemas.device import DeviceClaimIn, RemoteDeviceConnectIn

    monkeypatch.setattr(config_module.settings, "ANDROID_MULTI_NODE_ENABLED", True)
    monkeypatch.setattr(config_module.settings, "ADB_SCAN_MODE", "worker")
    monkeypatch.setattr(config_module.settings, "ATP_LOCAL_MODE", False)

    # 1) /runtime exposes adb_scan_mode and android_multi_node_enabled
    rt = runtime.get_runtime_identity()
    assert rt.adb_scan_mode == "worker"
    assert rt.android_multi_node_enabled is True
    caps = runtime.get_runtime_capabilities()
    assert caps["android_multi_node_enabled"] is True

    # 2) /devices/connect requires explicit worker_id in multi-node mode even if only 1 worker is online
    async def run_connect_and_claim():
        engine = create_async_engine("sqlite+aiosqlite:///:memory:")
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        maker = async_sessionmaker(engine, expire_on_commit=False)
        async with maker() as db:
            admin = User(username="adm", email="adm@example.com", hashed_password="x", role=UserRole.admin)
            unclaimed = Device(serial="emu-claim", worker_id=None, status=DeviceStatus.online)
            db.add_all([admin, unclaimed])
            await db.commit()

            with pytest.raises(HTTPException) as exc_conn:
                await devices.connect_remote_adb_device(
                    body=RemoteDeviceConnectIn(host="192.168.1.99", port=5555, worker_id=None),
                    db=db,
                    _=admin,
                )
            assert exc_conn.value.status_code == 400
            assert "worker_id" in str(exc_conn.value.detail)

            # Invalid worker_id characters rejected with 422
            with pytest.raises(HTTPException) as exc_bad_wid:
                await devices.claim_device_worker(
                    device_id=unclaimed.id,
                    body=DeviceClaimIn(worker_id="bad:worker id*"),
                    db=db,
                    current_user=admin,
                )
            assert exc_bad_wid.value.status_code == 422

            # Valid claim to online worker succeeds and forbids silent rebind without force=True
            async def fake_online(wid: str):
                return {"worker_id": wid, "hostname": "WIN-HOST-A", "instance_generation": 1}

            monkeypatch.setattr(devices, "get_android_worker", fake_online)
            claimed = await devices.claim_device_worker(
                device_id=unclaimed.id,
                body=DeviceClaimIn(worker_id="win-a"),
                db=db,
                current_user=admin,
            )
            assert claimed.worker_id == "win-a"
            assert claimed.worker_hostname == "WIN-HOST-A"

            with pytest.raises(HTTPException) as exc_rebind:
                await devices.claim_device_worker(
                    device_id=unclaimed.id,
                    body=DeviceClaimIn(worker_id="win-b"),
                    db=db,
                    current_user=admin,
                )
            assert exc_rebind.value.status_code == 409

            # Expired aggregate scan ID returns 404 instead of falling through to PENDING/queued
            async def fake_missing_agg(_scan_id: str):
                return None

            monkeypatch.setattr(devices, "_load_aggregate_scan", fake_missing_agg)
            with pytest.raises(HTTPException) as exc_expired:
                await devices.get_scan_status(scan_id=f"agg-{uuid4()}", db=db, _=admin)
            assert exc_expired.value.status_code == 404
            assert "scan_expired" in str(exc_expired.value.detail)
        await engine.dispose()

    asyncio.run(run_connect_and_claim())

    # 3) deploy-linux.sh -HookMode exits 0 cleanly when ATP_SKIP_DEPLOY=1 (never blocks git push)
    repo_root = Path(__file__).resolve().parents[3]
    proc = subprocess.run(
        ["bash", str(repo_root / "scripts" / "deploy-linux.sh"), "-HookMode"],
        env={**__import__("os").environ, "ATP_SKIP_DEPLOY": "1"},
        capture_output=True,
        text=True,
        timeout=5,
    )
    assert proc.returncode == 0
