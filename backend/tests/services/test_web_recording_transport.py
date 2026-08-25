import asyncio
import base64
import json

import pytest

from app.core.config import settings
from app.services import web_recording_transport as transport
from app.web_recording_worker import WebRecordingWorker


class _FakeRedis:
    def __init__(self):
        self.values: dict[str, str] = {}
        self.lists: dict[str, list[str]] = {}
        self.expirations: dict[str, int] = {}
        self.closed = False

    async def set(self, key, value, ex=None):
        self.values[key] = value
        if ex is not None:
            self.expirations[key] = ex

    async def get(self, key):
        return self.values.get(key)

    async def delete(self, *keys):
        deleted = 0
        for key in keys:
            if key in self.values:
                deleted += 1
                self.values.pop(key, None)
            self.lists.pop(key, None)
        return deleted

    async def mget(self, keys):
        return [self.values.get(key) for key in keys]

    async def scan_iter(self, match=None):
        for key in self.values:
            if match is None or key.startswith(match.removesuffix("*")):
                yield key

    async def rpush(self, key, value):
        self.lists.setdefault(key, []).append(value)

    async def expire(self, key, ttl):
        self.expirations[key] = ttl

    async def blpop(self, key, timeout=0):
        values = self.lists.get(key) or []
        if values:
            return key, values.pop(0)
        return None

    async def aclose(self):
        self.closed = True


def test_worker_keys_and_selection_are_deterministic(monkeypatch):
    monkeypatch.setattr(transport.settings, "WEB_RECORDER_WORKER_QUEUE_PREFIX", "test:web")
    assert transport.worker_key("one") == "test:web:workers:one"
    assert transport.worker_queue_key("one") == "test:web:one"
    assert transport.response_key("request") == "test:web:replies:request"
    assert transport.session_key("session") == "test:web:sessions:session"

    async def run():
        return await transport.choose_recording_worker()

    monkeypatch.setattr(
        transport,
        "list_recording_workers",
        lambda: asyncio.sleep(
            0,
            result=[
                {"worker_id": "busy", "active_sessions": 2, "capacity": 2},
                {"worker_id": "idle-b", "active_sessions": 0, "capacity": 2},
                {"worker_id": "idle-a", "active_sessions": 0, "capacity": 2},
            ],
        ),
    )
    assert asyncio.run(run())["worker_id"] == "idle-a"


def test_list_recording_workers_filters_invalid_heartbeats(monkeypatch):
    redis = _FakeRedis()
    redis.values[transport.worker_key("valid")] = json.dumps(
        {"worker_id": "valid", "active_sessions": 0, "capacity": 2}
    )
    redis.values[transport.worker_key("missing-id")] = json.dumps({"capacity": 2})
    redis.values[transport.worker_key("invalid-json")] = "{"
    redis.values[transport.worker_key("not-an-object")] = json.dumps(["worker"])
    monkeypatch.setattr(transport, "get_async_redis", lambda: redis)

    workers = asyncio.run(transport.list_recording_workers())

    assert workers == [{"worker_id": "valid", "active_sessions": 0, "capacity": 2}]


def test_transport_lazy_redis_factory_reports_missing_stub(monkeypatch):
    monkeypatch.setattr(transport, "_redis_client", object())

    with pytest.raises(transport.WebRecordingTransportError, match="Redis"):
        transport.get_async_redis()


def test_remote_manager_routes_session_and_screenshot(monkeypatch):
    redis = _FakeRedis()
    monkeypatch.setattr(transport, "get_async_redis", lambda: redis)
    monkeypatch.setattr(
        transport,
        "choose_recording_worker",
        lambda: asyncio.sleep(0, result={"worker_id": "worker-a", "active_sessions": 0, "capacity": 2}),
    )
    calls = []

    async def request(worker_id, action, **payload):
        calls.append((worker_id, action, payload))
        if action == "start":
            return {"ok": True, "snapshot": {"id": payload["session_id"], "status": "recording", "project_id": 7}}
        if action == "snapshot":
            return {"ok": True, "snapshot": {"id": payload["session_id"], "status": "recording"}}
        if action == "screenshot":
            return {"ok": True, "data": base64.b64encode(b"png").decode("ascii")}
        return {"ok": True, "snapshot": {"id": payload["session_id"], "status": "stopped"}}

    monkeypatch.setattr(transport, "send_recording_command", request)
    manager = transport.RemoteWebRecordingManager()

    async def run():
        started = await manager.start({"project_id": 7, "start_url": "https://example.com"}, owner_id=3)
        session_id = started["id"]
        assert (await manager.get(session_id, 3))["status"] == "recording"
        assert await manager.screenshot(session_id, 3) == b"png"
        assert (await manager.stop(session_id, 3))["status"] == "stopped"
        return session_id

    session_id = asyncio.run(run())
    assert transport.session_key(session_id) in redis.values
    assert asyncio.run(manager.get(session_id, 3))["status"] == "stopped"
    assert [call[1] for call in calls] == ["start", "snapshot", "screenshot", "stop"]


def test_remote_manager_retries_explicit_busy_on_another_worker(monkeypatch):
    redis = _FakeRedis()
    monkeypatch.setattr(transport, "get_async_redis", lambda: redis)
    monkeypatch.setattr(
        transport,
        "choose_recording_worker",
        lambda: asyncio.sleep(0, result={"worker_id": "worker-a", "active_sessions": 0, "capacity": 1}),
    )
    monkeypatch.setattr(
        transport,
        "list_recording_workers",
        lambda: asyncio.sleep(
            0,
            result=[
                {"worker_id": "worker-a", "active_sessions": 1, "capacity": 1},
                {"worker_id": "worker-b", "active_sessions": 0, "capacity": 1},
            ],
        ),
    )
    calls: list[tuple[str, str]] = []

    async def request(worker_id, action, **payload):
        calls.append((worker_id, action))
        if worker_id == "worker-a":
            return {"ok": False, "code": "busy", "error": "worker is full"}
        return {"ok": True, "snapshot": {"id": payload["session_id"], "status": "recording"}}

    monkeypatch.setattr(transport, "send_recording_command", request)
    started = asyncio.run(
        transport.RemoteWebRecordingManager().start({"project_id": 7, "start_url": "https://example.com"}, owner_id=3)
    )

    assert started["status"] == "recording"
    assert [worker_id for worker_id, _ in calls] == ["worker-a", "worker-b"]
    session_metadata = json.loads(redis.values[transport.session_key(started["id"])])
    assert session_metadata["worker_id"] == "worker-b"


def test_remote_manager_does_not_retry_command_timeout(monkeypatch):
    monkeypatch.setattr(
        transport,
        "choose_recording_worker",
        lambda: asyncio.sleep(0, result={"worker_id": "worker-a", "active_sessions": 0, "capacity": 1}),
    )
    calls: list[str] = []

    async def request(worker_id, action, **payload):
        calls.append(worker_id)
        raise transport.WebRecordingTransportError("worker response timeout")

    async def unexpected_worker_listing():
        raise AssertionError("a command timeout must not trigger a fallback listing")

    monkeypatch.setattr(transport, "send_recording_command", request)
    monkeypatch.setattr(transport, "list_recording_workers", unexpected_worker_listing)

    with pytest.raises(transport.WebRecordingTransportError, match="timeout"):
        asyncio.run(
            transport.RemoteWebRecordingManager().start(
                {"project_id": 7, "start_url": "https://example.com"}, owner_id=3
            )
        )
    assert calls == ["worker-a"]


def test_remote_manager_stops_worker_when_start_reply_has_no_snapshot(monkeypatch):
    monkeypatch.setattr(
        transport,
        "choose_recording_worker",
        lambda: asyncio.sleep(0, result={"worker_id": "worker-a", "active_sessions": 0, "capacity": 1}),
    )
    calls: list[str] = []

    async def request(worker_id, action, **payload):
        calls.append(action)
        if action == "start":
            return {"ok": True}
        return {"ok": True, "snapshot": {"id": payload["session_id"], "status": "stopped"}}

    monkeypatch.setattr(transport, "send_recording_command", request)

    with pytest.raises(transport.WebRecordingTransportError, match="未返回会话状态"):
        asyncio.run(
            transport.RemoteWebRecordingManager().start(
                {"project_id": 7, "start_url": "https://example.com"}, owner_id=3
            )
        )

    assert calls == ["start", "stop"]


def test_remote_manager_rejects_wrong_owner(monkeypatch):
    redis = _FakeRedis()
    monkeypatch.setattr(transport, "get_async_redis", lambda: redis)
    asyncio.run(transport.save_session_metadata("s1", owner_id=5, project_id=1, worker_id="w1"))

    with pytest.raises(transport.WebRecordingTransportError) as error:
        asyncio.run(transport.RemoteWebRecordingManager().get("s1", owner_id=6))
    assert error.value.status_code == 404


def test_session_route_refreshes_configured_ttl(monkeypatch):
    redis = _FakeRedis()
    monkeypatch.setattr(transport, "get_async_redis", lambda: redis)
    monkeypatch.setattr(transport.settings, "WEB_RECORDER_SESSION_TTL_SECONDS", 900)

    asyncio.run(transport.save_session_metadata("s1", owner_id=5, project_id=1, worker_id="w1"))
    assert redis.expirations[transport.session_key("s1")] == 900

    asyncio.run(transport.touch_session_metadata("s1"))
    assert redis.expirations[transport.session_key("s1")] == 900


def test_worker_dispatches_commands_and_enforces_capacity(monkeypatch):
    import app.web_recording_worker as worker_module

    class _Session:
        def __init__(self, **kwargs):
            self.session_id = kwargs["session_id"]
            self.status = "starting"
            self.steps = []

        async def start(self):
            self.status = "recording"

        async def screenshot(self):
            return b"worker-png"

        async def stop(self):
            self.status = "stopped"

        def snapshot(self):
            return {"id": self.session_id, "status": self.status, "steps": self.steps}

    monkeypatch.setattr(worker_module, "WebRecordingSession", _Session)
    worker = WebRecordingWorker("worker-a")
    worker.capacity = 1
    command = {
        "action": "start",
        "session_id": "s1",
        "owner_id": 2,
        "payload": {"project_id": 1, "start_url": "https://example.com"},
    }

    started = asyncio.run(worker._dispatch(command))
    assert started["ok"] is True
    assert asyncio.run(worker._dispatch({"action": "snapshot", "session_id": "s1"}))["ok"] is True
    screenshot = asyncio.run(worker._dispatch({"action": "screenshot", "session_id": "s1"}))
    assert base64.b64decode(screenshot["data"]) == b"worker-png"

    busy = asyncio.run(worker._dispatch({**command, "session_id": "s2"}))
    assert busy == {"ok": False, "code": "busy", "error": "录制 Worker 已达到并发上限"}
    stopped = asyncio.run(worker._dispatch({"action": "stop", "session_id": "s1"}))
    assert stopped["snapshot"]["status"] == "stopped"
    assert asyncio.run(worker._dispatch({"action": "snapshot", "session_id": "s1"}))["code"] == "not_found"


def test_worker_health_file_tracks_successful_registration(monkeypatch, tmp_path):
    import app.web_recording_worker as worker_module

    health_file = tmp_path / "web-recorder.ready"
    monkeypatch.setenv("WEB_RECORDER_HEALTH_FILE", str(health_file))
    redis = _FakeRedis()
    worker = WebRecordingWorker("worker-a")

    async def stop_after_probe(*_args, **_kwargs):
        assert health_file.exists()
        worker.stop_event.set()
        return None

    redis.blpop = stop_after_probe
    monkeypatch.setattr(worker_module._redis_client, "get_async_redis", lambda **_kwargs: redis)
    monkeypatch.setattr(worker_module, "register_recording_worker", lambda *args, **kwargs: asyncio.sleep(0))
    monkeypatch.setattr(worker_module, "unregister_recording_worker", lambda *args, **kwargs: asyncio.sleep(0))

    asyncio.run(worker.run())

    assert not health_file.exists()


def test_worker_clears_stale_health_file_before_first_registration(monkeypatch, tmp_path):
    import app.web_recording_worker as worker_module

    health_file = tmp_path / "web-recorder.ready"
    health_file.touch()
    monkeypatch.setenv("WEB_RECORDER_HEALTH_FILE", str(health_file))
    redis = _FakeRedis()
    worker = WebRecordingWorker("worker-a")

    async def fail_registration(*_args, **_kwargs):
        raise RuntimeError("redis connection reset")

    async def stop_after_probe(*_args, **_kwargs):
        assert not health_file.exists()
        worker.stop_event.set()
        return None

    redis.blpop = stop_after_probe
    monkeypatch.setattr(worker_module._redis_client, "get_async_redis", lambda **_kwargs: redis)
    monkeypatch.setattr(worker_module, "register_recording_worker", fail_registration)
    monkeypatch.setattr(worker_module, "unregister_recording_worker", lambda *args, **kwargs: asyncio.sleep(0))

    asyncio.run(worker.run())

    assert not health_file.exists()


def test_worker_heartbeat_retries_after_unwrapped_client_error(monkeypatch, tmp_path):
    import app.web_recording_worker as worker_module

    health_file = tmp_path / "web-recorder.ready"
    monkeypatch.setenv("WEB_RECORDER_HEALTH_FILE", str(health_file))
    worker = WebRecordingWorker("worker-a")
    worker._touch_health_file()

    async def fail_registration(*_args, **_kwargs):
        raise RuntimeError("redis connection reset")

    monkeypatch.setattr(worker_module, "register_recording_worker", fail_registration)
    monkeypatch.setattr(worker_module.settings, "WEB_RECORDER_WORKER_HEARTBEAT_SECONDS", 1)

    async def run_probe():
        with pytest.raises(asyncio.TimeoutError):
            await asyncio.wait_for(worker._heartbeat_loop(_FakeRedis()), timeout=0.1)

    asyncio.run(run_probe())

    assert not health_file.exists()


def test_worker_returns_start_failure_and_not_ready_screenshot(monkeypatch):
    import app.web_recording_worker as worker_module

    class _FailingSession:
        def __init__(self, **kwargs):
            self.session_id = kwargs["session_id"]

        async def start(self):
            raise RuntimeError("browser unavailable")

        def snapshot(self):
            return {"id": self.session_id, "status": "error"}

    monkeypatch.setattr(worker_module, "WebRecordingSession", _FailingSession)
    worker = WebRecordingWorker("worker-a")
    command = {
        "action": "start",
        "session_id": "s1",
        "owner_id": 2,
        "payload": {"project_id": 1, "start_url": "https://example.com"},
    }

    failed = asyncio.run(worker._dispatch(command))

    assert failed["code"] == "start_failed"
    assert worker.sessions == {}
    assert worker.pending_sessions == set()

    class _NotReadySession:
        def __init__(self, **kwargs):
            self.session_id = kwargs["session_id"]

        async def start(self):
            return None

        async def screenshot(self):
            raise RuntimeError("page is not ready")

        async def stop(self):
            return None

        def snapshot(self):
            return {"id": self.session_id, "status": "recording"}

    monkeypatch.setattr(worker_module, "WebRecordingSession", _NotReadySession)
    assert asyncio.run(worker._dispatch(command))["ok"] is True
    not_ready = asyncio.run(worker._dispatch({"action": "screenshot", "session_id": "s1"}))
    assert not_ready == {"ok": False, "code": "not_ready", "error": "page is not ready"}


def test_worker_replies_and_handles_malformed_or_failed_commands(monkeypatch):
    worker = WebRecordingWorker("worker-a")
    redis = _FakeRedis()

    asyncio.run(worker._reply(redis, {}, {"ok": True}))
    asyncio.run(worker._reply(redis, {"reply_key": "reply"}, {"ok": True}))
    assert json.loads(redis.lists["reply"][0]) == {"ok": True}
    assert redis.expirations["reply"] >= 5

    asyncio.run(worker._process(redis, "{"))
    asyncio.run(worker._process(redis, "[]"))

    async def fail_dispatch(_command):
        raise RuntimeError("dispatch failed")

    monkeypatch.setattr(worker, "_dispatch", fail_dispatch)
    asyncio.run(worker._process(redis, json.dumps({"reply_key": "failed"})))
    failure = json.loads(redis.lists["failed"][0])
    assert failure["code"] == "worker_error"


def test_send_recording_command_uses_reply_queue(monkeypatch):
    redis = _FakeRedis()
    captured = {}

    async def rpush(key, value):
        await _FakeRedis.rpush(redis, key, value)
        if key == transport.worker_queue_key("worker-a"):
            command = json.loads(value)
            await _FakeRedis.rpush(redis, command["reply_key"], json.dumps({"ok": True, "value": 1}))

    redis.rpush = rpush

    def get_redis(**kwargs):
        captured.update(kwargs)
        return redis

    monkeypatch.setattr(transport, "get_async_redis", get_redis)
    response = asyncio.run(transport.send_recording_command("worker-a", "snapshot", session_id="s1"))
    assert response == {"ok": True, "value": 1}
    assert captured["socket_timeout"] == settings.WEB_RECORDER_COMMAND_TIMEOUT_SECONDS + 1
