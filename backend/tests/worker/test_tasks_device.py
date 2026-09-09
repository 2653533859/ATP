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
    result = tasks_device.heartbeat_android_worker(task)

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
