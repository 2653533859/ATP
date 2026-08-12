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

    assert result == {"worker_id": "win-a", "status": "online", "queues": ["mobile_special"]}
    assert task.calls == [{"countdown": 15, "queue": "mobile_special"}]
