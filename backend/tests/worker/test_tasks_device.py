import base64
import sys
import types
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))


def test_scan_adb_devices_skip_sync_when_scan_failed(monkeypatch):
    from app.core import config as config_module

    class FakeCeleryApp:
        def task(self, *args, **kwargs):
            def decorator(func):
                return func

            return decorator

    fake_celery_module = types.SimpleNamespace(celery_app=FakeCeleryApp())
    monkeypatch.setitem(sys.modules, "app.worker.celery_app", fake_celery_module)

    from app.worker import tasks_device

    sync_calls = 0
    session_factory_calls = 0

    monkeypatch.setattr(config_module.settings, "ADB_SCAN_ENABLED", True)
    monkeypatch.setattr(tasks_device, "scan_devices", lambda: None)

    def fake_sync(session, scanned):
        nonlocal sync_calls
        sync_calls += 1

    monkeypatch.setattr(tasks_device, "sync_devices_to_db_sync", fake_sync)

    def fake_session_factory():
        nonlocal session_factory_calls
        session_factory_calls += 1
        raise AssertionError("scan failed 时不应创建数据库会话")

    fake_database_module = types.SimpleNamespace(sync_session_factory=fake_session_factory)
    monkeypatch.setitem(sys.modules, "app.core.database", fake_database_module)

    result = tasks_device.scan_adb_devices()

    assert result == {"status": "failed", "error": "ADB 扫描失败", "count": 0}
    assert sync_calls == 0
    assert session_factory_calls == 0


def test_android_worker_heartbeat_registers_and_reschedules(monkeypatch):
    from app.core import config as config_module
    from app.worker import tasks_device

    class FakeTask:
        def __init__(self):
            self.calls = []

        def apply_async(self, **kwargs):
            self.calls.append(kwargs)

    async def fake_register(worker_id, *, queues):
        return {"worker_id": worker_id, "status": "online", "queues": queues}

    monkeypatch.setattr(config_module.settings, "ANDROID_WORKER_ID", "win-a")
    monkeypatch.setattr(config_module.settings, "ANDROID_WORKER_QUEUE", "mobile_special")
    monkeypatch.setattr(config_module.settings, "ANDROID_WORKER_HEARTBEAT_SECONDS", 15)
    monkeypatch.setattr(tasks_device, "register_android_worker", fake_register)
    monkeypatch.setattr(tasks_device, "run_async", lambda coroutine: __import__("asyncio").run(coroutine))

    task = FakeTask()
    hb_task = tasks_device.heartbeat_android_worker
    runner = getattr(getattr(hb_task, "run", None), "__func__", hb_task)
    result = runner(task)

    assert result == {"worker_id": "win-a", "status": "online", "queues": ["android", "mobile_special"]}
    assert task.calls == [{"countdown": 15, "queue": "android"}]


def test_periodic_scan_is_not_queued_without_remote_worker(monkeypatch):
    from app.core import config as config_module
    from app.worker import tasks_device

    async def no_workers():
        return []

    calls = []
    monkeypatch.setattr(config_module.settings, "ADB_SCAN_ENABLED", True)
    monkeypatch.setattr(config_module.settings, "ADB_SCAN_MODE", "worker")
    monkeypatch.setattr(tasks_device, "list_android_workers", no_workers)
    monkeypatch.setattr(tasks_device, "run_async", lambda coroutine: __import__("asyncio").run(coroutine))
    monkeypatch.setattr(
        tasks_device.scan_adb_devices,
        "apply_async",
        lambda **kwargs: calls.append(kwargs),
        raising=False,
    )

    result = tasks_device.dispatch_android_device_scan()

    assert result == {"status": "no_worker"}
    assert calls == []


def test_periodic_scan_uses_expiring_android_control_queue(monkeypatch):
    from app.core import config as config_module
    from app.worker import tasks_device

    async def online_workers():
        return [{"worker_id": "win-a", "status": "online"}]

    calls = []
    monkeypatch.setattr(config_module.settings, "ADB_SCAN_ENABLED", True)
    monkeypatch.setattr(config_module.settings, "ADB_SCAN_MODE", "worker")
    monkeypatch.setattr(config_module.settings, "ADB_SCAN_INTERVAL", 15)
    monkeypatch.setattr(tasks_device, "list_android_workers", online_workers)
    monkeypatch.setattr(tasks_device, "run_async", lambda coroutine: __import__("asyncio").run(coroutine))
    monkeypatch.setattr(
        tasks_device.scan_adb_devices,
        "apply_async",
        lambda **kwargs: calls.append(kwargs),
        raising=False,
    )

    result = tasks_device.dispatch_android_device_scan()

    assert result == {"status": "queued"}
    assert calls == [{"queue": "android", "ignore_result": True, "expires": 15}]


def test_android_worker_device_operation_returns_json_safe_results(monkeypatch):
    from app.worker import tasks_device

    calls = []
    fake_mirror = types.SimpleNamespace(
        _adb_screenshot=lambda serial: b"png",
        _adb_input=lambda serial, *args: calls.append((serial, args)) or True,
        _adb_ui_target_diagnostic=lambda serial, x, y: (
            {"text": "登录", "x": x, "y": y},
            {"status": "found", "code": None},
        ),
    )
    monkeypatch.setitem(sys.modules, "app.api.v1.device_mirror", fake_mirror)
    task = tasks_device.run_android_device_operation
    runner = getattr(task, "run", task)

    screenshot = runner("screenshot", "WIN-DEVICE", {})
    tap = runner("tap", "WIN-DEVICE", {"x": 10, "y": 20})
    target = runner("ui_target", "WIN-DEVICE", {"x": 10, "y": 20})

    assert screenshot == {"ok": True, "data_base64": base64.b64encode(b"png").decode("ascii"), "error": None}
    assert tap == {"ok": True, "error": None}
    assert target == {
        "ok": True,
        "target": {"text": "登录", "x": 10, "y": 20},
        "diagnostic": {"status": "found", "code": None},
    }
    assert calls == [("WIN-DEVICE", ("tap", "10", "20"))]


def test_android_worker_forwards_mirror_key_and_text(monkeypatch):
    from app.api.v1 import device_mirror
    from app.worker.tasks_device import run_android_device_operation

    calls = []
    monkeypatch.setattr(device_mirror, "_adb_input", lambda serial, *args: calls.append((serial, args)) or True)
    runner = getattr(run_android_device_operation, "run", run_android_device_operation)

    assert runner("keyevent", "WIN-DEVICE", {"keycode": "3"}) == {"ok": True, "error": None}
    assert runner("text", "WIN-DEVICE", {"text": "hello%sworld"}) == {"ok": True, "error": None}
    assert runner("keyevent", "WIN-DEVICE", {})["ok"] is False
    assert calls == [("WIN-DEVICE", ("keyevent", "3")), ("WIN-DEVICE", ("text", "hello%sworld"))]


def test_android_worker_handles_ui_anchors_operation(monkeypatch):
    from app.worker import tasks_device

    fake_mirror = types.SimpleNamespace(
        _adb_ui_anchors_diagnostic=lambda serial: (
            {"text": "工作台", "resourceId": "com.demo:id/home", "contentDesc": None, "packageName": serial},
            {"status": "found", "code": None},
        )
    )
    monkeypatch.setitem(sys.modules, "app.api.v1.device_mirror", fake_mirror)
    runner = getattr(tasks_device.run_android_device_operation, "run", tasks_device.run_android_device_operation)

    result = runner("ui_anchors", "WIN-DEVICE", {})

    assert result == {
        "ok": True,
        "anchors": {
            "text": "工作台",
            "resourceId": "com.demo:id/home",
            "contentDesc": None,
            "packageName": "WIN-DEVICE",
        },
        "diagnostic": {"status": "found", "code": None},
    }


def test_worker_registry_lifecycle_conflict_exit_and_expiry_rotation(monkeypatch):
    import json
    import pytest
    from app.core import config as config_module
    from app.services import android_worker_registry as reg
    from app.worker import celery_app as celery_module

    store: dict[str, str] = {}

    class FakeDictRedis:
        def __init__(self):
            self.closed = False

        def get(self, key):
            return store.get(key)

        def set(self, key, value, ex=None, nx=False):
            if nx and key in store:
                return False
            store[key] = value
            return True

        def delete(self, key):
            return 1 if store.pop(key, None) is not None else 0

        def close(self):
            self.closed = True

    reg.clear_current_worker_runtime()
    monkeypatch.setattr(config_module.settings, "ANDROID_WORKER_ID", "win-a")
    monkeypatch.setattr(config_module.settings, "ANDROID_MULTI_NODE_ENABLED", True)

    client1 = FakeDictRedis()
    monkeypatch.setattr(reg, "_sync_redis_client", lambda: client1)

    try:
        # 1. Worker A1 starts cleanly and claims slot
        celery_module._schedule_android_worker_heartbeat()
        gen1 = reg.get_current_worker_generation()
        assert gen1 is not None
        assert reg.verify_worker_execution_target(expected_worker_id="win-a", expected_generation=gen1) == (True, None)

        # 2. Duplicate Worker A2 with same ID must abort with SystemExit(1) and mark conflict
        client2 = FakeDictRedis()
        monkeypatch.setattr(reg, "_sync_redis_client", lambda: client2)
        with pytest.raises(SystemExit) as exc_info:
            celery_module._schedule_android_worker_heartbeat()
        assert exc_info.value.code == 1
        assert client2.closed is True
        assert reg.verify_worker_execution_target(expected_worker_id="win-a", expected_generation=gen1) == (
            False,
            "worker_conflict_detected",
        )

        # Restore A1 state and simulate TTL expiry with nobody else taking over -> rotates generation
        reg.set_current_worker_runtime(
            "win-a",
            celery_module._android_heartbeat_thread.instance_generation,
            celery_module._android_heartbeat_thread.instance_token,
        )
        store.clear()
        assert celery_module._android_heartbeat_thread.beat_once() is True
        gen2 = reg.get_current_worker_generation()
        assert gen2 is not None and gen2 > gen1
        assert reg.verify_worker_execution_target(expected_worker_id="win-a", expected_generation=gen1) == (
            False,
            "worker_generation_mismatch",
        )

        # Simulate usurpation by another live worker -> conflict callback & rejection
        conflicts: list[bool] = []
        celery_module._android_heartbeat_thread._on_conflict = lambda: conflicts.append(True)
        store[reg.worker_key("win-a")] = json.dumps({"worker_id": "win-a", "instance_token": "other-owner"})
        assert celery_module._android_heartbeat_thread.beat_once() is False
        assert celery_module._android_heartbeat_thread.conflict_detected is True
        assert conflicts == [True]
    finally:
        # 3. Graceful solo shutdown releases slot and resets runtime
        celery_module._shutdown_android_worker_heartbeat()
        reg.clear_current_worker_runtime()


def test_offline_worker_convergence_respects_grace_period_and_reconnect(monkeypatch):
    from sqlalchemy import create_engine, select
    from sqlalchemy.orm import sessionmaker

    from app.core import config as config_module
    from app.models.base import Base
    from app.models.bootstrap import load_all_models
    from app.models.device import Device, DeviceStatus
    from app.services import android_worker_registry as reg
    from app.worker import tasks_device

    load_all_models()
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    SessionLocal = sessionmaker(bind=engine, expire_on_commit=False)

    with SessionLocal() as s:
        s.add_all(
            [
                Device(serial="emu-1", worker_id="win-lost", status=DeviceStatus.online),
                Device(serial="emu-1", worker_id="win-alive", status=DeviceStatus.online),
            ]
        )
        s.commit()

    store: dict[str, str] = {}

    class FakeRedis:
        def get(self, key):
            return store.get(key)

        def set(self, key, value, ex=None, nx=False):
            if nx and key in store:
                return False
            store[key] = value
            return True

        def delete(self, key):
            store.pop(key, None)

        def close(self):
            pass

    monkeypatch.setattr(config_module.settings, "ANDROID_WORKER_OFFLINE_GRACE_SECONDS", 15)
    monkeypatch.setitem(sys.modules, "app.core.database", types.SimpleNamespace(sync_session_factory=SessionLocal))
    monkeypatch.setattr(tasks_device, "_sync_redis_client", FakeRedis)

    # First check: win-lost missing, enters grace window -> NOT marked offline yet
    now_ref = [1000.0]
    monkeypatch.setattr(tasks_device.time, "time", lambda: now_ref[0])
    assert tasks_device._reconcile_offline_worker_devices({"win-alive"}) == []
    with SessionLocal() as s:
        statuses = {d.worker_id: d.status for d in s.scalars(select(Device)).all()}
        assert statuses["win-lost"] == DeviceStatus.online

    # Reconnect before grace elapses -> missing key cleared, stays online
    store[reg.worker_key("win-lost")] = '{"worker_id":"win-lost"}'
    now_ref[0] = 1020.0
    assert tasks_device._reconcile_offline_worker_devices(set()) == []
    store.pop(reg.worker_key("win-lost"), None)

    # Goes missing again -> grace elapses -> marked offline; win-alive untouched
    now_ref[0] = 2000.0
    assert tasks_device._reconcile_offline_worker_devices({"win-alive"}) == []
    now_ref[0] = 2016.0
    assert tasks_device._reconcile_offline_worker_devices({"win-alive"}) == ["win-lost"]
    with SessionLocal() as s:
        statuses = {d.worker_id: d.status for d in s.scalars(select(Device)).all()}
        assert statuses["win-lost"] == DeviceStatus.offline
        assert statuses["win-alive"] == DeviceStatus.online
    engine.dispose()
