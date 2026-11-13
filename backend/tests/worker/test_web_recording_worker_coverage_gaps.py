"""补充 backend/app/web_recording_worker.py 的覆盖率缺口。

覆盖健康文件读写的失败分支、启动参数校验、启动成功/失败、截图与停止指令、
坏指令与 worker_error、心跳注册失败，以及 run() 主循环的 Redis 异常路径、
连接关闭钩子与 main() 的启动链路。
"""

import asyncio
import base64
import json
from types import SimpleNamespace

from app import web_recording_worker as worker_module
from app.core import redis_client as _redis_client
from app.services.web_recording_transport import WebRecordingTransportError


def _patch_quick_sleep(monkeypatch, worker):
    """把心跳/重试睡眠替换为立即置位 stop_event 的伪睡眠（真实等待 0 秒）。"""
    real_sleep = asyncio.sleep

    async def _quick_sleep(_seconds):
        worker.stop_event.set()
        await real_sleep(0)

    monkeypatch.setattr(worker_module.asyncio, "sleep", _quick_sleep)


class _FakeSession:
    def __init__(self, session_id="s1"):
        self.session_id = session_id
        self.stopped = False

    def snapshot(self):
        return {"session_id": self.session_id, "status": "recording"}

    async def stop(self):
        self.stopped = True


class _FakeClient:
    """最小 Redis 替身：blpop 取空时置位 stop_event，避免主循环挂起。"""

    def __init__(self, worker, items=None):
        self.worker = worker
        self.items = list(items or [])
        self.pushes = []
        self.deleted = []
        self.closed = False

    async def blpop(self, _key, timeout=None):
        if self.items:
            return self.items.pop(0)
        self.worker.stop_event.set()
        return None

    async def rpush(self, key, value):
        self.pushes.append((key, value))

    async def expire(self, key, ttl):
        return True

    async def set(self, *_args, **_kwargs):
        return True

    async def delete(self, key):
        self.deleted.append(key)

    async def aclose(self):
        self.closed = True


def test_health_file_helpers_noop_without_env(monkeypatch):
    monkeypatch.delenv("WEB_RECORDER_HEALTH_FILE", raising=False)
    worker = worker_module.WebRecordingWorker(worker_id="w-health")

    worker._touch_health_file()
    worker._clear_health_file()

    assert worker._health_file() is None


def test_health_file_errors_are_logged(monkeypatch, tmp_path):
    blocker = tmp_path / "blocker"
    blocker.write_text("file", encoding="utf-8")
    monkeypatch.setenv("WEB_RECORDER_HEALTH_FILE", str(blocker / "sub" / "health"))
    worker = worker_module.WebRecordingWorker(worker_id="w-health-fail")

    worker._touch_health_file()  # mkdir/touch 失败不得抛出

    as_dir = tmp_path / "health-dir"
    as_dir.mkdir()
    monkeypatch.setenv("WEB_RECORDER_HEALTH_FILE", str(as_dir))
    worker._clear_health_file()  # unlink 目录失败不得抛出


def test_start_rejects_invalid_payload_shapes():
    worker = worker_module.WebRecordingWorker(worker_id="w-start")

    result = asyncio.run(worker._start({"session_id": "s1", "owner_id": 1, "payload": "not-a-dict"}))
    assert result == {"ok": False, "code": "invalid", "error": "录制启动参数无效"}

    result = asyncio.run(
        worker._start(
            {
                "session_id": "",
                "owner_id": 1,
                "payload": {"start_url": "https://example.com", "project_id": 1},
            }
        )
    )
    assert result["ok"] is False
    assert result["code"] == "invalid"
    assert "session_id 或 owner_id 无效" in result["error"]


def test_dispatch_unknown_action_and_missing_session():
    worker = worker_module.WebRecordingWorker(worker_id="w-dispatch")
    worker.sessions["s1"] = _FakeSession("s1")

    missing = asyncio.run(worker._dispatch({"action": "snapshot", "session_id": "nope"}))
    assert missing == {"ok": False, "code": "not_found", "error": "录制会话不存在或已结束"}

    unknown = asyncio.run(worker._dispatch({"action": "bogus", "session_id": "s1"}))
    assert unknown["code"] == "invalid"
    assert "不支持的录制 Worker 操作" in unknown["error"]


def test_process_swallows_reply_failure():
    worker = worker_module.WebRecordingWorker(worker_id="w-reply")
    worker.sessions["s1"] = _FakeSession("s1")

    class _ReplyBoomClient:
        async def rpush(self, *_args, **_kwargs):
            raise RuntimeError("redis write failed")

    command = json.dumps({"action": "snapshot", "session_id": "s1", "reply_key": "rk"})
    asyncio.run(worker._process(_ReplyBoomClient(), command))  # 不得抛出


def test_heartbeat_returns_when_already_stopped(monkeypatch):
    calls = []

    async def _register(*_args, **_kwargs):
        calls.append(1)

    monkeypatch.setattr(worker_module, "register_recording_worker", _register, raising=False)
    worker = worker_module.WebRecordingWorker(worker_id="w-hb-stop")
    worker.stop_event.set()

    asyncio.run(worker._heartbeat_loop(SimpleNamespace()))

    assert calls == []


def test_heartbeat_registers_and_touches_health_file(monkeypatch, tmp_path):
    calls = []

    async def _register(worker_id, *, active_sessions, capacity, client):
        calls.append((worker_id, active_sessions, capacity))

    monkeypatch.setattr(worker_module, "register_recording_worker", _register, raising=False)
    health = tmp_path / "worker-health"
    monkeypatch.setenv("WEB_RECORDER_HEALTH_FILE", str(health))
    worker = worker_module.WebRecordingWorker(worker_id="w-hb")
    _patch_quick_sleep(monkeypatch, worker)

    asyncio.run(worker._heartbeat_loop(SimpleNamespace()))

    assert calls == [("w-hb", 0, worker.capacity)]
    assert health.exists()


def test_heartbeat_transport_error_clears_health_file(monkeypatch, tmp_path):
    async def _register(*_args, **_kwargs):
        raise WebRecordingTransportError("redis down")

    monkeypatch.setattr(worker_module, "register_recording_worker", _register, raising=False)
    health = tmp_path / "worker-health"
    health.write_text("ok", encoding="utf-8")
    monkeypatch.setenv("WEB_RECORDER_HEALTH_FILE", str(health))
    worker = worker_module.WebRecordingWorker(worker_id="w-hb-fail")
    _patch_quick_sleep(monkeypatch, worker)

    asyncio.run(worker._heartbeat_loop(SimpleNamespace()))

    assert not health.exists()


def test_heartbeat_generic_failure_clears_health_file(monkeypatch, tmp_path):
    async def _register(*_args, **_kwargs):
        raise RuntimeError("pool exhausted")

    monkeypatch.setattr(worker_module, "register_recording_worker", _register, raising=False)
    health = tmp_path / "worker-health"
    health.write_text("ok", encoding="utf-8")
    monkeypatch.setenv("WEB_RECORDER_HEALTH_FILE", str(health))
    worker = worker_module.WebRecordingWorker(worker_id="w-hb-crash")
    _patch_quick_sleep(monkeypatch, worker)

    asyncio.run(worker._heartbeat_loop(SimpleNamespace()))

    assert not health.exists()


def _run_common_patches(monkeypatch, client, register, unregister):
    monkeypatch.setattr(worker_module, "register_recording_worker", register, raising=False)
    monkeypatch.setattr(worker_module, "unregister_recording_worker", unregister, raising=False)
    # worker 模块与测试模块在模块级 sys.modules 替换的会话里可能绑定到不同的
    # redis_client 对象（收集顺序不同导致），统一到测试文件持有并补丁的对象，
    # 保证 get_async_redis / close_async_redis 的补丁对 worker 可见。
    monkeypatch.setattr(worker_module, "_redis_client", _redis_client, raising=False)
    monkeypatch.setattr(_redis_client, "get_async_redis", lambda socket_timeout=None: client, raising=False)
    monkeypatch.delattr(_redis_client, "close_async_redis", raising=False)
    monkeypatch.setattr(worker_module.settings, "WEB_RECORDER_WORKER_HEARTBEAT_SECONDS", 1)


def test_run_handles_boot_registration_failure_and_processes_command(monkeypatch, tmp_path):
    events = []

    async def _register(worker_id, *, active_sessions, capacity, client):
        events.append(worker_id)
        if len(events) == 1:
            raise WebRecordingTransportError("redis boot down")

    async def _unregister(worker_id, *, client):
        events.append(("unregister", worker_id))

    worker = worker_module.WebRecordingWorker(worker_id="w-run")
    session = _FakeSession("s1")
    worker.sessions["s1"] = session
    client = _FakeClient(
        worker,
        items=[("queue", json.dumps({"action": "snapshot", "session_id": "s1", "reply_key": "reply:1"}))],
    )
    _run_common_patches(monkeypatch, client, _register, _unregister)
    monkeypatch.setenv("WEB_RECORDER_HEALTH_FILE", str(tmp_path / "worker-health"))

    asyncio.run(worker.run())

    assert events[0] == "w-run"  # 首次注册触发 TransportError 分支后仍继续运行
    assert ("unregister", "w-run") in events
    assert client.pushes and client.pushes[0][0] == "reply:1"
    payload = json.loads(client.pushes[0][1])
    assert payload["ok"] is True
    assert payload["snapshot"]["session_id"] == "s1"
    assert session.stopped is True
    assert client.closed is True  # 无 close_async_redis 时回退 aclose


def test_run_survives_blpop_transport_and_generic_errors(monkeypatch):
    async def _register(*_args, **_kwargs):
        return None

    async def _unregister(*_args, **_kwargs):
        return None

    class _FlakyClient(_FakeClient):
        def __init__(self, worker, error):
            super().__init__(worker)
            self.error = error
            self.calls = 0

        async def blpop(self, _key, timeout=None):
            self.calls += 1
            if self.calls == 1:
                raise self.error
            self.worker.stop_event.set()
            return None

    for error in (WebRecordingTransportError("control plane down"), RuntimeError("pool exhausted")):
        worker = worker_module.WebRecordingWorker(worker_id="w-flaky")
        client = _FlakyClient(worker, error)
        _run_common_patches(monkeypatch, client, _register, _unregister)

        asyncio.run(worker.run())

        assert client.calls == 2


def test_main_registers_signals_and_runs_worker(monkeypatch):
    created = []

    class _FakeWorker:
        def __init__(self):
            self.worker_id = "w-main"
            self.capacity = 2
            self.stop_event = asyncio.Event()
            self.ran = False
            created.append(self)

        async def run(self):
            self.ran = True

    monkeypatch.setattr(worker_module, "WebRecordingWorker", _FakeWorker)

    asyncio.run(worker_module.main())

    assert created and created[0].ran is True


def test_reply_skipped_without_reply_key():
    class _ExplodingClient:
        async def rpush(self, *_args, **_kwargs):
            raise AssertionError("reply should not be sent")

    worker = worker_module.WebRecordingWorker(worker_id="w-noreply")
    worker.sessions["s1"] = _FakeSession("s1")
    asyncio.run(worker._process(_ExplodingClient(), json.dumps({"action": "snapshot", "session_id": "s1"})))


def test_start_busy_when_capacity_reached():
    worker = worker_module.WebRecordingWorker(worker_id="w-busy")
    worker.capacity = 1
    worker.sessions["x"] = _FakeSession("x")

    result = asyncio.run(
        worker._start({"session_id": "s2", "owner_id": 1, "payload": {"start_url": "https://example.com"}})
    )

    assert result == {"ok": False, "code": "busy", "error": "录制 Worker 已达到并发上限"}


def test_dispatch_start_creates_and_starts_session(monkeypatch):
    started = []

    async def _fake_start(self):
        started.append(self.session_id)

    monkeypatch.setattr(worker_module.WebRecordingSession, "start", _fake_start)
    worker = worker_module.WebRecordingWorker(worker_id="w-create")

    result = asyncio.run(
        worker._dispatch(
            {
                "action": "start",
                "session_id": "s-new",
                "owner_id": 7,
                "payload": {"start_url": "https://example.com", "project_id": 1},
            }
        )
    )

    assert result["ok"] is True
    assert started == ["s-new"]
    assert "s-new" in worker.sessions
    assert worker.pending_sessions == set()
    assert result["snapshot"]["id"] == "s-new"


def test_dispatch_start_reports_session_start_failure(monkeypatch):
    async def _failing_start(self):
        raise RuntimeError("chromium missing")

    monkeypatch.setattr(worker_module.WebRecordingSession, "start", _failing_start)
    worker = worker_module.WebRecordingWorker(worker_id="w-create-fail")

    result = asyncio.run(
        worker._start(
            {
                "session_id": "s-fail",
                "owner_id": 7,
                "payload": {"start_url": "https://example.com", "project_id": 1},
            }
        )
    )

    assert result["ok"] is False
    assert result["code"] == "start_failed"
    assert "chromium missing" in result["error"]
    assert result["snapshot"]["id"] == "s-fail"
    assert "s-fail" not in worker.sessions


def test_dispatch_screenshot_and_stop():
    worker = worker_module.WebRecordingWorker(worker_id="w-shot")

    class _ShotSession(_FakeSession):
        def __init__(self, session_id, error=None):
            super().__init__(session_id)
            self.error = error

        async def screenshot(self):
            if self.error is not None:
                raise self.error
            return b"png-bytes"

    worker.sessions["s-ok"] = _ShotSession("s-ok")
    worker.sessions["s-not-ready"] = _ShotSession("s-not-ready", RuntimeError("still starting"))

    shot = asyncio.run(worker._dispatch({"action": "screenshot", "session_id": "s-ok"}))
    assert shot["ok"] is True
    assert base64.b64decode(shot["data"]) == b"png-bytes"

    not_ready = asyncio.run(worker._dispatch({"action": "screenshot", "session_id": "s-not-ready"}))
    assert not_ready == {"ok": False, "code": "not_ready", "error": "still starting"}

    stopped = asyncio.run(worker._dispatch({"action": "stop", "session_id": "s-ok"}))
    assert stopped["ok"] is True
    assert stopped["snapshot"]["session_id"] == "s-ok"
    assert "s-ok" not in worker.sessions


def test_process_ignores_malformed_commands():
    class _ExplodingClient:
        async def rpush(self, *_args, **_kwargs):
            raise AssertionError("reply should not be sent")

    worker = worker_module.WebRecordingWorker(worker_id="w-garbage")
    client = _ExplodingClient()

    asyncio.run(worker._process(client, "not-json"))
    asyncio.run(worker._process(client, json.dumps(["not", "a", "dict"])))


def test_process_reports_worker_error():
    worker = worker_module.WebRecordingWorker(worker_id="w-error")

    class _BrokenSession(_FakeSession):
        def snapshot(self):
            raise RuntimeError("snapshot exploded")

    worker.sessions["s1"] = _BrokenSession("s1")
    client = _FakeClient(worker)
    command = json.dumps({"action": "snapshot", "session_id": "s1", "reply_key": "reply:err"})

    asyncio.run(worker._process(client, command))

    assert client.pushes and client.pushes[0][0] == "reply:err"
    payload = json.loads(client.pushes[0][1])
    assert payload["ok"] is False
    assert payload["code"] == "worker_error"
    assert "snapshot exploded" in payload["error"]


def test_run_survives_boot_registration_crash(monkeypatch):
    async def _register(*_args, **_kwargs):
        if not getattr(_register, "failed", False):
            _register.failed = True
            raise RuntimeError("pool exhausted")

    async def _unregister(*_args, **_kwargs):
        return None

    worker = worker_module.WebRecordingWorker(worker_id="w-boot-crash")
    client = _FakeClient(worker)
    _run_common_patches(monkeypatch, client, _register, _unregister)

    asyncio.run(worker.run())

    assert client.closed is True


def test_run_uses_close_async_redis_hook(monkeypatch):
    closed = []

    async def _register(*_args, **_kwargs):
        return None

    async def _unregister(*_args, **_kwargs):
        return None

    async def _close_async_redis(client):
        closed.append(client)

    worker = worker_module.WebRecordingWorker(worker_id="w-hook")
    client = _FakeClient(worker)
    _run_common_patches(monkeypatch, client, _register, _unregister)
    monkeypatch.setattr(_redis_client, "close_async_redis", _close_async_redis, raising=False)

    asyncio.run(worker.run())

    assert closed == [client]


def test_run_without_any_close_hook(monkeypatch):
    async def _register(*_args, **_kwargs):
        return None

    async def _unregister(*_args, **_kwargs):
        return None

    worker = worker_module.WebRecordingWorker(worker_id="w-bare")

    class _BareClient:
        async def blpop(self, _key, timeout=None):
            worker.stop_event.set()
            return None

    client = _BareClient()
    _run_common_patches(monkeypatch, client, _register, _unregister)

    asyncio.run(worker.run())  # 无 close_async_redis 且无 aclose：不得抛出


def test_main_skips_platform_missing_signals(monkeypatch):
    created = []

    class _FakeWorker:
        def __init__(self):
            self.worker_id = "w-signals"
            self.capacity = 1
            self.stop_event = asyncio.Event()
            self.ran = False
            created.append(self)

        async def run(self):
            self.ran = True

    monkeypatch.setattr(worker_module, "WebRecordingWorker", _FakeWorker)
    monkeypatch.setattr(worker_module, "signal", SimpleNamespace(SIGINT=None, SIGTERM=None))

    asyncio.run(worker_module.main())

    assert created and created[0].ran is True


def test_worker_start_propagates_auto_assert_flag(monkeypatch):
    worker = worker_module.WebRecordingWorker(worker_id="w-auto-assert")
    created = []

    class _FakeAutoSession:
        def __init__(self, **kwargs):
            created.append(kwargs)
            self.session_id = kwargs["session_id"]
            self.auto_assert = kwargs["auto_assert"]

        async def start(self):
            return None

        def snapshot(self):
            return {"session_id": self.session_id, "status": "recording", "auto_assert": self.auto_assert}

    monkeypatch.setattr(worker_module, "WebRecordingSession", _FakeAutoSession)

    result = asyncio.run(
        worker._start(
            {
                "session_id": "s-no-assert",
                "owner_id": 7,
                "payload": {"start_url": "https://example.com", "project_id": 1, "auto_assert": False},
            }
        )
    )

    assert result["ok"] is True
    assert created[0]["auto_assert"] is False
    assert result["snapshot"]["auto_assert"] is False
