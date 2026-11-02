"""补齐 remote_node_agent.py 的未覆盖分支：隧道生命周期、本地令牌与出站长连代理。"""

import asyncio
import base64
import json
import socket
import subprocess
import sys
from types import SimpleNamespace

import pytest
import websockets.asyncio.client as ws_client
from fastapi import FastAPI
from fastapi.responses import Response
from httpx import TimeoutException

import app.services.remote_node_agent as agent
from app.core.config import settings
from app.models.bootstrap import load_all_models

load_all_models()


class _FakeProcess:
    """ssh 子进程替身：记录 terminate/kill/wait 调用。"""

    def __init__(self, *, returncode=None):
        self.returncode = returncode
        self.terminated = 0
        self.killed = 0
        self.waits = 0

    def terminate(self):
        self.terminated += 1

    def kill(self):
        self.killed += 1

    async def wait(self):
        self.waits += 1
        return 0


class _TimeoutWaitProcess(_FakeProcess):
    """首次 wait 抛出 TimeoutError，kill 后再次 wait 正常返回。"""

    async def wait(self):
        self.waits += 1
        if self.waits == 1:
            raise TimeoutError
        return 0


class _FakeStreamWriter:
    def __init__(self):
        self.closed = False

    def close(self):
        self.closed = True

    async def wait_closed(self):
        return None


class _FakeStopEvent:
    """可控 stop event：raise_on_wait=True 时 wait() 立即抛 TimeoutError。"""

    def __init__(self, *, raise_on_wait=False):
        self._set = False
        self._raise_on_wait = raise_on_wait

    def is_set(self):
        return self._set

    def set(self):
        self._set = True

    async def wait(self):
        if self._raise_on_wait:
            raise TimeoutError
        if self._set:
            return True
        await asyncio.sleep(3600)


class _SelfSettingEvent:
    """wait() 被调用即置位的 stop event，用于让心跳循环自然退出。"""

    def __init__(self):
        self._set = False

    def is_set(self):
        return self._set

    def set(self):
        self._set = True

    async def wait(self):
        self._set = True
        return True


class _FakeWS:
    """反向通道 WebSocket 替身：按序吐出预置帧并记录 send 内容。"""

    def __init__(self, frames=(), on_exhausted=None):
        self._frames = list(frames)
        self.sent = []
        self._on_exhausted = on_exhausted

    async def send(self, payload):
        self.sent.append(payload)
        await asyncio.sleep(0)

    def __aiter__(self):
        return self

    async def __anext__(self):
        await asyncio.sleep(0)
        if self._frames:
            return self._frames.pop(0)
        if self._on_exhausted is not None:
            callback, self._on_exhausted = self._on_exhausted, None
            callback()
        raise StopAsyncIteration


class _ConnectFactory:
    """websockets connect 替身：既作工厂又作异步上下文管理器。"""

    def __init__(self, ws, *, enter_error=None, before_enter=None):
        self.calls = []
        self._ws = ws
        self._enter_error = enter_error
        self._before_enter = before_enter

    def __call__(self, url, *, additional_headers, max_size):
        self.calls.append({"url": url, "headers": additional_headers, "max_size": max_size})
        return self

    async def __aenter__(self):
        if self._before_enter is not None:
            self._before_enter()
        if self._enter_error is not None:
            raise self._enter_error
        return self._ws

    async def __aexit__(self, *_exc):
        return False


async def _no_tunnel():
    return None


def _configure_tunnel(monkeypatch, tmp_path, port):
    """准备 SSH 身份文件与一致的 loopback 隧道配置。"""
    key = tmp_path / "node_key"
    key.write_text("PRIVATE KEY", encoding="utf-8")
    hosts = tmp_path / "known_hosts"
    hosts.write_text("cloud.example.test ssh-ed25519 AAAA", encoding="utf-8")
    monkeypatch.setattr(settings, "REMOTE_NODE_SSH_HOST", "cloud.example.test")
    monkeypatch.setattr(settings, "REMOTE_NODE_SSH_PORT", 2222)
    monkeypatch.setattr(settings, "REMOTE_NODE_SSH_USER", "node")
    monkeypatch.setattr(settings, "REMOTE_NODE_SSH_KEY_FILE", str(key))
    monkeypatch.setattr(settings, "REMOTE_NODE_SSH_KNOWN_HOSTS", str(hosts))
    monkeypatch.setattr(settings, "REMOTE_NODE_TUNNEL_PORT", port)
    monkeypatch.setattr(settings, "CLOUD_SYNC_URL", f"http://127.0.0.1:{port}")


def _install_fake_asyncio(monkeypatch, *, open_connection, spawn, sleep):
    """只替换 agent 模块内的 asyncio 引用，避免污染全局 asyncio。"""
    monkeypatch.setattr(
        agent,
        "asyncio",
        SimpleNamespace(
            open_connection=open_connection,
            create_subprocess_exec=spawn,
            sleep=sleep,
            subprocess=asyncio.subprocess,
        ),
    )


def _enable_cloud(monkeypatch):
    monkeypatch.setattr(settings, "CLOUD_SYNC_URL", "http://127.0.0.1:8000")
    monkeypatch.setattr(settings, "CLOUD_SYNC_API_KEY", "cloud-secret")


def test_node_ws_url_rejects_credentials_path_and_missing_netloc():
    with pytest.raises(ValueError, match="origin without credentials or path"):
        agent._node_ws_url("https://user:pass@cloud.example.test", "win-1")
    with pytest.raises(ValueError, match="origin without credentials or path"):
        agent._node_ws_url("https://cloud.example.test/api", "win-1")
    with pytest.raises(ValueError, match="origin without credentials or path"):
        agent._node_ws_url("https:///only-path", "win-1")
    assert agent._node_ws_url("https://cloud.example.test/", "win-1") == (
        "wss://cloud.example.test/api/v1/remote-nodes/connect/win-1"
    )
    assert agent._node_ws_url("http://localhost:8000", "win-1").startswith("ws://localhost:8000/")


def test_private_tunnel_disabled_without_ssh_host(monkeypatch):
    monkeypatch.setattr(settings, "REMOTE_NODE_SSH_HOST", "")
    assert asyncio.run(agent._start_private_tunnel()) is None


def test_private_tunnel_requires_identity_and_known_hosts(monkeypatch, tmp_path):
    _configure_tunnel(monkeypatch, tmp_path, 18026)
    monkeypatch.setattr(settings, "REMOTE_NODE_SSH_KEY_FILE", str(tmp_path / "absent-key"))
    with pytest.raises(ValueError, match="identity or known_hosts is missing"):
        asyncio.run(agent._start_private_tunnel())


def test_private_tunnel_rejects_occupied_local_port(monkeypatch, tmp_path):
    listener = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        listener.bind(("127.0.0.1", 0))
        listener.listen(1)
        port = listener.getsockname()[1]
        _configure_tunnel(monkeypatch, tmp_path, port)
        with pytest.raises(ValueError, match="already occupied"):
            asyncio.run(agent._start_private_tunnel())
    finally:
        listener.close()


def test_private_tunnel_spawns_ssh_and_waits_for_ready_port(monkeypatch, tmp_path):
    _configure_tunnel(monkeypatch, tmp_path, 18023)
    process = _FakeProcess()
    writer = _FakeStreamWriter()
    attempts = []

    async def fake_open_connection(host, port):
        attempts.append((host, port))
        if len(attempts) <= 2:
            raise OSError("connection refused")
        return object(), writer

    spawn_calls = []

    async def fake_spawn(*args, **kwargs):
        spawn_calls.append((args, kwargs))
        return process

    sleeps = []

    async def fake_sleep(delay):
        sleeps.append(delay)

    _install_fake_asyncio(monkeypatch, open_connection=fake_open_connection, spawn=fake_spawn, sleep=fake_sleep)

    assert asyncio.run(agent._start_private_tunnel()) is process
    assert sleeps == [0.25]
    assert writer.closed is True
    assert attempts[0] == ("127.0.0.1", 18023)
    args, kwargs = spawn_calls[0]
    assert args[0] == "ssh"
    assert "127.0.0.1:18023:127.0.0.1:8000" in args
    assert "node@cloud.example.test" in args
    assert kwargs["stdin"] is asyncio.subprocess.DEVNULL
    expected_flags = getattr(subprocess, "CREATE_NO_WINDOW", 0) if sys.platform == "win32" else 0
    assert kwargs["creationflags"] == expected_flags


def test_private_tunnel_creation_flags_for_both_platforms(monkeypatch, tmp_path):
    _configure_tunnel(monkeypatch, tmp_path, 18024)
    process = _FakeProcess()
    spawn_kwargs = []
    attempts = []

    async def fake_open_connection(_host, _port):
        attempts.append(1)
        if len(attempts) % 2 == 1:
            raise OSError("nothing listening")
        return object(), _FakeStreamWriter()

    async def fake_spawn(*_args, **kwargs):
        spawn_kwargs.append(kwargs)
        return process

    async def fake_sleep(_delay):
        return None

    _install_fake_asyncio(monkeypatch, open_connection=fake_open_connection, spawn=fake_spawn, sleep=fake_sleep)

    for platform, expected in (("win32", getattr(subprocess, "CREATE_NO_WINDOW", 0)), ("darwin", 0)):
        monkeypatch.setattr(sys, "platform", platform)
        asyncio.run(agent._start_private_tunnel())
        assert spawn_kwargs[-1]["creationflags"] == expected


def test_private_tunnel_reports_early_process_exit(monkeypatch, tmp_path):
    _configure_tunnel(monkeypatch, tmp_path, 18025)
    process = _FakeProcess(returncode=1)

    async def fake_open_connection(_host, _port):
        raise OSError("connection refused")

    async def fake_spawn(*_args, **_kwargs):
        return process

    async def fake_sleep(_delay):
        return None

    _install_fake_asyncio(monkeypatch, open_connection=fake_open_connection, spawn=fake_spawn, sleep=fake_sleep)
    with pytest.raises(ConnectionError, match="exited before opening"):
        asyncio.run(agent._start_private_tunnel())


def test_private_tunnel_gives_up_after_retry_budget(monkeypatch, tmp_path):
    _configure_tunnel(monkeypatch, tmp_path, 18025)
    process = _FakeProcess()
    sleeps = []

    async def fake_open_connection(_host, _port):
        raise OSError("connection refused")

    async def fake_spawn(*_args, **_kwargs):
        return process

    async def fake_sleep(delay):
        sleeps.append(delay)

    _install_fake_asyncio(monkeypatch, open_connection=fake_open_connection, spawn=fake_spawn, sleep=fake_sleep)
    with pytest.raises(ConnectionError, match="did not become ready"):
        asyncio.run(agent._start_private_tunnel())
    assert len(sleeps) == 20
    assert process.terminated == 1
    assert process.waits == 1


class _AdminSession:
    """AsyncSessionLocal 替身：scalar() 返回预置的本地管理员。"""

    def __init__(self, user):
        self._user = user

    async def __aenter__(self):
        return self

    async def __aexit__(self, *_exc):
        return False

    async def scalar(self, _statement):
        return self._user


def test_local_admin_token_mints_token_or_raises(monkeypatch):
    monkeypatch.setattr(agent, "AsyncSessionLocal", lambda: _AdminSession(SimpleNamespace(username="admin")))
    token = asyncio.run(agent._local_admin_token())
    assert isinstance(token, str) and token
    monkeypatch.setattr(agent, "AsyncSessionLocal", lambda: _AdminSession(None))
    with pytest.raises(RuntimeError, match="No active local admin"):
        asyncio.run(agent._local_admin_token())


def test_dispatch_node_request_rejects_unsafe_paths():
    app = FastAPI()
    cases = [
        "/health",
        "https://cloud.example.test/api/v1/projects",
        "//host/api/v1/projects",
        "/api/v1/projects/../../secrets",
        "/api/v1/remote-nodes/self",
    ]
    for path in cases:
        frame = {"request_id": "r-1", "method": "GET", "path": path, "headers": {}, "body": ""}
        result = asyncio.run(agent.dispatch_node_request(app, frame))
        assert result == {"type": "response", "request_id": "r-1", "status": 400, "headers": {}, "body": ""}


def test_dispatch_node_request_rejects_bad_or_oversized_body(monkeypatch):
    app = FastAPI()
    monkeypatch.setattr(agent, "MAX_PROXY_BYTES", 4)
    frame = {"request_id": "r-2", "method": "POST", "path": "/api/v1/projects", "headers": {}, "body": "%%%"}
    assert asyncio.run(agent.dispatch_node_request(app, frame))["status"] == 502
    frame["body"] = base64.b64encode(b"12345").decode("ascii")
    assert asyncio.run(agent.dispatch_node_request(app, frame))["status"] == 502


def test_dispatch_node_request_maps_timeouts_and_internal_errors(monkeypatch):
    async def token():
        return "local-token"

    monkeypatch.setattr(agent, "_local_admin_token", token)

    timeout_app = FastAPI()

    @timeout_app.get("/api/v1/slow")
    async def slow():
        raise asyncio.TimeoutError

    result = asyncio.run(agent.dispatch_node_request(timeout_app, {"request_id": "r-3", "path": "/api/v1/slow"}))
    assert result["status"] == 504

    httpx_app = FastAPI()

    @httpx_app.get("/api/v1/slow-http")
    async def slow_http():
        raise TimeoutException("read timed out")

    result = asyncio.run(agent.dispatch_node_request(httpx_app, {"request_id": "r-4", "path": "/api/v1/slow-http"}))
    assert result["status"] == 504

    boom_app = FastAPI()

    @boom_app.get("/api/v1/boom")
    async def boom():
        raise RuntimeError("adapter crashed")

    result = asyncio.run(agent.dispatch_node_request(boom_app, {"request_id": "r-5", "path": "/api/v1/boom"}))
    assert result["status"] == 502


def test_dispatch_node_request_maps_oversized_response(monkeypatch):
    monkeypatch.setattr(agent, "MAX_PROXY_BYTES", 2)

    async def token():
        return "local-token"

    monkeypatch.setattr(agent, "_local_admin_token", token)
    app = FastAPI()

    @app.get("/api/v1/big")
    async def big():
        return Response(content=b"abc", media_type="application/json")

    result = asyncio.run(agent.dispatch_node_request(app, {"request_id": "r-6", "path": "/api/v1/big"}))
    assert result["status"] == 413
    assert base64.b64decode(result["body"]) == b'{"detail":"Remote response exceeds channel limit"}'
    assert result["headers"] == {"content-type": "application/json"}


def test_dispatch_node_request_maps_token_failure(monkeypatch):
    async def token():
        raise RuntimeError("no admin")

    monkeypatch.setattr(agent, "_local_admin_token", token)
    result = asyncio.run(agent.dispatch_node_request(FastAPI(), {"request_id": "r-7", "path": "/api/v1/projects"}))
    assert result["status"] == 502


def _exercise_agent_retry(monkeypatch, tunnel=None):
    """跑一轮：连接失败后清理隧道并退出循环。"""
    stop_event = asyncio.Event()

    async def start_tunnel():
        return tunnel

    monkeypatch.setattr(agent, "_start_private_tunnel", start_tunnel)
    connect = _ConnectFactory(_FakeWS(), enter_error=RuntimeError("ws closed"), before_enter=stop_event.set)
    monkeypatch.setattr(ws_client, "connect", connect)
    monkeypatch.setattr(agent, "get_machine_id", lambda: "machine-retry")
    _enable_cloud(monkeypatch)
    asyncio.run(agent.run_local_node_agent(FastAPI(), stop_event))
    return connect


def test_run_local_node_agent_disabled_without_cloud_settings(monkeypatch):
    connect = _ConnectFactory(_FakeWS())
    monkeypatch.setattr(ws_client, "connect", connect)
    monkeypatch.setattr(settings, "CLOUD_SYNC_URL", "")
    monkeypatch.setattr(settings, "CLOUD_SYNC_API_KEY", "secret")
    asyncio.run(agent.run_local_node_agent(FastAPI(), asyncio.Event()))
    assert connect.calls == []


def test_run_local_node_agent_ignores_insecure_origin(monkeypatch):
    monkeypatch.setattr(settings, "CLOUD_SYNC_URL", "http://192.168.1.50:8000")
    monkeypatch.setattr(settings, "CLOUD_SYNC_API_KEY", "secret")
    monkeypatch.setattr(agent, "get_machine_id", lambda: "machine-1")
    asyncio.run(agent.run_local_node_agent(FastAPI(), asyncio.Event()))


def test_run_local_node_agent_dispatches_frames_and_heartbeats(monkeypatch):
    stop_event = asyncio.Event()
    ws = _FakeWS(
        frames=[
            json.dumps({"type": "other"}),
            json.dumps({"type": "request", "request_id": "req-1", "path": "/api/v1/projects"}),
        ]
    )
    connect = _ConnectFactory(ws)
    monkeypatch.setattr(ws_client, "connect", connect)
    monkeypatch.setattr(agent, "_start_private_tunnel", _no_tunnel)
    dispatched = []

    async def fake_dispatch(app, frame):
        dispatched.append((app, frame))
        await asyncio.sleep(0)
        stop_event.set()
        return {"type": "response", "request_id": frame["request_id"], "status": 200}

    monkeypatch.setattr(agent, "dispatch_node_request", fake_dispatch)
    monkeypatch.setattr(agent, "get_machine_id", lambda: "machine-42")
    monkeypatch.setattr(agent, "get_machine_name", lambda: "DESKTOP-TEST")
    _enable_cloud(monkeypatch)

    app = FastAPI()
    asyncio.run(agent.run_local_node_agent(app, stop_event))

    assert connect.calls == [
        {
            "url": "ws://127.0.0.1:8000/api/v1/remote-nodes/connect/machine-42",
            "headers": {"X-ATP-Api-Key": "cloud-secret"},
            "max_size": agent.MAX_PROXY_FRAME_BYTES,
        }
    ]
    assert dispatched == [(app, {"type": "request", "request_id": "req-1", "path": "/api/v1/projects"})]
    sent = [json.loads(item) for item in ws.sent]
    assert {"type": "response", "request_id": "req-1", "status": 200} in sent
    heartbeats = [item for item in sent if item.get("type") == "heartbeat"]
    assert heartbeats and heartbeats[0]["machine_name"] == "DESKTOP-TEST"


def test_run_local_node_agent_retries_when_connect_fails(monkeypatch):
    connect = _exercise_agent_retry(monkeypatch)
    assert len(connect.calls) == 1
    assert connect.calls[0]["url"].endswith("/connect/machine-retry")


def test_run_local_node_agent_terminates_failed_tunnel(monkeypatch):
    tunnel = _FakeProcess()
    _exercise_agent_retry(monkeypatch, tunnel)
    assert tunnel.terminated == 1
    assert tunnel.killed == 0
    assert tunnel.waits == 1


def test_run_local_node_agent_kills_tunnel_when_wait_times_out(monkeypatch):
    tunnel = _TimeoutWaitProcess()
    _exercise_agent_retry(monkeypatch, tunnel)
    assert tunnel.terminated == 1
    assert tunnel.killed == 1
    assert tunnel.waits == 2


def test_run_local_node_agent_skips_cleanup_for_exited_tunnel(monkeypatch):
    tunnel = _FakeProcess(returncode=0)
    _exercise_agent_retry(monkeypatch, tunnel)
    assert tunnel.terminated == 0
    assert tunnel.waits == 0


def test_run_local_node_agent_survives_pause_and_heartbeat_timeouts(monkeypatch):
    stop_event = _FakeStopEvent(raise_on_wait=True)
    ws = _FakeWS(frames=[json.dumps({"type": "other"})], on_exhausted=stop_event.set)
    connect = _ConnectFactory(ws)
    monkeypatch.setattr(ws_client, "connect", connect)
    monkeypatch.setattr(agent, "_start_private_tunnel", _no_tunnel)
    monkeypatch.setattr(agent, "get_machine_id", lambda: "machine-timeout")
    monkeypatch.setattr(agent, "get_machine_name", lambda: "DESKTOP-TIMEOUT")
    _enable_cloud(monkeypatch)

    asyncio.run(agent.run_local_node_agent(FastAPI(), stop_event))
    assert ws.sent
    assert len(connect.calls) == 1


def test_run_local_node_agent_heartbeat_exits_when_stop_requested(monkeypatch):
    stop_event = _SelfSettingEvent()
    ws = _FakeWS(frames=[json.dumps({"type": "other"})])
    connect = _ConnectFactory(ws)
    monkeypatch.setattr(ws_client, "connect", connect)
    monkeypatch.setattr(agent, "_start_private_tunnel", _no_tunnel)
    monkeypatch.setattr(agent, "get_machine_id", lambda: "machine-hb")
    monkeypatch.setattr(agent, "get_machine_name", lambda: "DESKTOP-HB")
    _enable_cloud(monkeypatch)

    asyncio.run(agent.run_local_node_agent(FastAPI(), stop_event))
    assert stop_event.is_set() is True
    heartbeats = [json.loads(item) for item in ws.sent]
    assert any(item.get("type") == "heartbeat" for item in heartbeats)
    assert len(connect.calls) == 1
