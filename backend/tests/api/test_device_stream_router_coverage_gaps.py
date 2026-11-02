"""补齐 device_stream/router.py 的未覆盖分支：WS 鉴权、触控端点与全双工流循环。"""

import asyncio
import concurrent.futures
import json
import threading
from types import SimpleNamespace

import pytest
from fastapi import HTTPException
from jwt import InvalidTokenError

from app.core.config import settings
from app.device_stream import router as ds_router
from app.device_stream.router import TouchEvent
from app.models.bootstrap import load_all_models

load_all_models()


def _user():
    return SimpleNamespace(id=7, username="engineer", is_active=True)


class _ScalarResult:
    def __init__(self, value=None):
        self._value = value

    def scalar_one_or_none(self):
        return self._value


class _WsSession:
    """_get_ws_user 使用的 AsyncSessionLocal 替身，可注入查询结果或构造期异常。"""

    def __init__(self, user=None, *, enter_error=None):
        self._user = user
        self._enter_error = enter_error

    async def __aenter__(self):
        if self._enter_error is not None:
            raise self._enter_error
        return self

    async def __aexit__(self, *_exc):
        return False

    async def execute(self, _statement):
        return _ScalarResult(self._user)


class _FakeWebSocket:
    """最小 WebSocket 替身：记录 accept/send/close，receive_text 从文本队列取帧。

    文本队列耗尽后置位 received_all 并挂起，等待对流侧结束任务后被取消；
    wake_first_send 模式用于让 recv 侧唤醒被挂起的 get_chunk 指令。
    """

    def __init__(self, texts=(), cookies=None, query_params=None, wake_first_send=None):
        self._texts = list(texts)
        self.cookies = dict(cookies or {})
        self.query_params = dict(query_params or {})
        self._wake_first_send = wake_first_send
        self.accepted = 0
        self.sent_bytes = []
        self.closed = []
        self.received_all = threading.Event()

    async def accept(self):
        self.accepted += 1

    async def close(self, code=1000):
        self.closed.append(code)

    async def send_bytes(self, chunk):
        self.sent_bytes.append(chunk)

    async def receive_text(self):
        if self._wake_first_send is not None:
            while not self._wake_first_send:
                await asyncio.sleep(0)
            future = self._wake_first_send.pop(0)
            if not future.done():
                future.set_result(None)
            raise ds_router.WebSocketDisconnect(1006)
        if self._texts:
            return self._texts.pop(0)
        self.received_all.set()
        await asyncio.sleep(3600)


class _WaitingStream:
    """get_chunk 先等待 recv 侧消费完全部控制帧，再返回 None 结束推流。"""

    def __init__(self, ready: threading.Event):
        self._ready = ready
        self.closed = []

    def get_chunk(self, _timeout=1.0):
        self._ready.wait(timeout=5)
        return None

    def close(self):
        self.closed.append(True)


class _ManualExecutor(concurrent.futures.ThreadPoolExecutor):
    """确定性执行器：get_chunk 挂起等待外部指令，其余调用同步完成。"""

    def __init__(self):
        super().__init__(max_workers=1)
        self.calls = []
        self.pending = []

    def submit(self, fn, /, *args, **kwargs):
        self.calls.append((getattr(fn, "__name__", ""), args))
        future = concurrent.futures.Future()
        if getattr(fn, "__name__", "") == "get_chunk":
            self.pending.append(future)
        else:
            future.set_result(fn(*args, **kwargs))
        return future


def _patch_user(monkeypatch):
    async def fake_get_user(_websocket):
        return _user()

    monkeypatch.setattr(ds_router, "_get_ws_user", fake_get_user)


def _patch_manager(monkeypatch, **overrides):
    monkeypatch.setattr(ds_router, "scrcpy_manager", SimpleNamespace(**overrides))


def test_ws_user_requires_token():
    assert asyncio.run(ds_router._get_ws_user(_FakeWebSocket())) is None


def test_ws_user_accepts_cookie_token(monkeypatch):
    user = _user()
    monkeypatch.setattr(ds_router, "decode_token", lambda _token: {"type": "access", "sub": "engineer"})
    monkeypatch.setattr(ds_router, "AsyncSessionLocal", lambda: _WsSession(user))
    ws = _FakeWebSocket(cookies={settings.ACCESS_COOKIE_NAME: "cookie-token"})
    assert asyncio.run(ds_router._get_ws_user(ws)) is user


def test_ws_user_accepts_query_token(monkeypatch):
    user = _user()
    seen = []

    def fake_decode(token):
        seen.append(token)
        return {"type": "access", "sub": "engineer"}

    monkeypatch.setattr(ds_router, "decode_token", fake_decode)
    monkeypatch.setattr(ds_router, "AsyncSessionLocal", lambda: _WsSession(user))
    ws = _FakeWebSocket(query_params={"token": "query-token"})
    assert asyncio.run(ds_router._get_ws_user(ws)) is user
    assert seen == ["query-token"]


def test_ws_user_rejects_wrong_token_type_or_missing_subject(monkeypatch):
    ws = _FakeWebSocket(query_params={"token": "t"})
    monkeypatch.setattr(ds_router, "decode_token", lambda _token: {"type": "refresh", "sub": "engineer"})
    assert asyncio.run(ds_router._get_ws_user(ws)) is None
    monkeypatch.setattr(ds_router, "decode_token", lambda _token: {"type": "access"})
    assert asyncio.run(ds_router._get_ws_user(ws)) is None


def test_ws_user_rejects_invalid_token(monkeypatch):
    def reject(_token):
        raise InvalidTokenError("expired signature")

    monkeypatch.setattr(ds_router, "decode_token", reject)
    ws = _FakeWebSocket(cookies={settings.ACCESS_COOKIE_NAME: "broken"})
    assert asyncio.run(ds_router._get_ws_user(ws)) is None


def test_ws_user_rejects_missing_or_inactive_user(monkeypatch):
    monkeypatch.setattr(ds_router, "decode_token", lambda _token: {"type": "access", "sub": "ghost"})
    ws = _FakeWebSocket(query_params={"token": "t"})
    monkeypatch.setattr(ds_router, "AsyncSessionLocal", lambda: _WsSession(None))
    assert asyncio.run(ds_router._get_ws_user(ws)) is None
    inactive = SimpleNamespace(id=8, username="ghost", is_active=False)
    monkeypatch.setattr(ds_router, "AsyncSessionLocal", lambda: _WsSession(inactive))
    assert asyncio.run(ds_router._get_ws_user(ws)) is None


def test_ws_user_returns_none_when_database_lookup_fails(monkeypatch):
    monkeypatch.setattr(ds_router, "decode_token", lambda _token: {"type": "access", "sub": "engineer"})
    monkeypatch.setattr(ds_router, "AsyncSessionLocal", lambda: _WsSession(enter_error=RuntimeError("db down")))
    ws = _FakeWebSocket(query_params={"token": "t"})
    assert asyncio.run(ds_router._get_ws_user(ws)) is None


def test_video_stream_rejects_unauthenticated_client():
    ws = _FakeWebSocket()
    asyncio.run(ds_router.scrcpy_video_stream(ws, "SER-0"))
    assert ws.closed == [ds_router.status.WS_1008_POLICY_VIOLATION]
    assert ws.accepted == 0


def test_video_stream_sends_chunks_and_skips_empty_ones(monkeypatch):
    _patch_user(monkeypatch)
    chunks = iter([b"\x00\x01", b"", b"\x02"])
    closed = []

    def get_chunk(_timeout):
        return next(chunks, None)

    stream = SimpleNamespace(get_chunk=get_chunk, close=lambda: closed.append(True))
    _patch_manager(monkeypatch, create_client_stream=lambda _serial: stream)
    ws = _FakeWebSocket()
    asyncio.run(ds_router.scrcpy_video_stream(ws, "SER-1"))
    assert ws.sent_bytes == [b"\x00\x01", b"\x02"]
    assert closed == [True]
    assert ws.closed == []


def test_video_stream_handles_touch_key_text_and_ignores_bad_frames(monkeypatch):
    _patch_user(monkeypatch)
    calls = []
    ws = _FakeWebSocket(
        texts=[
            json.dumps({"type": "touch", "action": 2, "x": 10, "y": 20, "w": 1080, "h": 1920}),
            json.dumps({"type": "touch"}),
            json.dumps({"type": "key", "keycode": 66}),
            json.dumps({"type": "text", "text": "你好"}),
            json.dumps({"type": "text"}),
            "{bad json",
            json.dumps({"type": "unknown"}),
        ]
    )
    stream = _WaitingStream(ws.received_all)
    _patch_manager(
        monkeypatch,
        create_client_stream=lambda _serial: stream,
        send_touch_event=lambda *args: calls.append(("touch", args)),
        send_key_event=lambda *args: calls.append(("key", args)),
        send_text_event=lambda *args: calls.append(("text", args)),
    )
    asyncio.run(ds_router.scrcpy_video_stream(ws, "SER-3"))
    assert calls == [
        ("touch", ("SER-3", 2, 10, 20, 1080, 1920)),
        ("touch", ("SER-3", 0, 0, 0, None, None)),
        ("key", ("SER-3", 66)),
        ("text", ("SER-3", "你好")),
        ("text", ("SER-3", "")),
    ]
    assert stream.closed == [True]
    assert ws.closed == []


def test_video_stream_closes_with_error_code_on_stream_failure(monkeypatch):
    _patch_user(monkeypatch)
    closed = []

    def boom(_timeout):
        raise RuntimeError("video socket died")

    stream = SimpleNamespace(get_chunk=boom, close=lambda: closed.append(True))
    _patch_manager(monkeypatch, create_client_stream=lambda _serial: stream)
    ws = _FakeWebSocket()
    asyncio.run(ds_router.scrcpy_video_stream(ws, "SER-4"))
    assert ws.closed == [4000]
    assert closed == [True]


def test_video_stream_treats_setup_disconnect_as_normal(monkeypatch):
    _patch_user(monkeypatch)

    def disconnect(_serial):
        raise ds_router.WebSocketDisconnect(1006)

    _patch_manager(monkeypatch, create_client_stream=disconnect)
    ws = _FakeWebSocket()
    asyncio.run(ds_router.scrcpy_video_stream(ws, "SER-5"))
    assert ws.closed == []
    assert ws.accepted == 1


def test_video_stream_reports_failure_when_setup_errors(monkeypatch):
    _patch_user(monkeypatch)

    def fail(_serial):
        raise RuntimeError("adb offline")

    _patch_manager(monkeypatch, create_client_stream=fail)
    ws = _FakeWebSocket()
    asyncio.run(ds_router.scrcpy_video_stream(ws, "SER-6"))
    assert ws.closed == [4000]


def test_video_stream_swallows_close_cleanup_errors(monkeypatch):
    _patch_user(monkeypatch)
    closed = []

    def boom(_timeout):
        raise RuntimeError("video socket died")

    def failing_close():
        closed.append(True)
        raise OSError("already gone")

    class _CloseFailsWebSocket(_FakeWebSocket):
        async def close(self, code=1000):
            raise RuntimeError("close failed")

    stream = SimpleNamespace(get_chunk=boom, close=failing_close)
    _patch_manager(monkeypatch, create_client_stream=lambda _serial: stream)
    asyncio.run(ds_router.scrcpy_video_stream(_CloseFailsWebSocket(), "SER-7"))
    assert closed == [True]


def test_video_stream_completes_when_send_and_recv_finish_together(monkeypatch):
    """send/recv 同步收尾时 pending 为空，不取消任何任务。"""
    _patch_user(monkeypatch)
    closed = []
    stream = SimpleNamespace(close=lambda: closed.append(True))

    def create_client_stream(_serial):
        return stream

    def get_chunk(_timeout):
        return None

    stream.get_chunk = get_chunk
    _patch_manager(monkeypatch, create_client_stream=create_client_stream)

    async def scenario():
        loop = asyncio.get_running_loop()
        executor = _ManualExecutor()
        loop.set_default_executor(executor)
        ws = _FakeWebSocket(wake_first_send=executor.pending)
        await ds_router.scrcpy_video_stream(ws, "SER-8")
        return ws, executor

    ws, executor = asyncio.run(scenario())
    assert ws.accepted == 1
    assert ws.closed == []
    assert closed == [True]
    assert [name for name, _args in executor.calls] == ["create_client_stream", "get_chunk"]


def test_send_touch_endpoint_delegates_to_manager(monkeypatch):
    calls = []
    _patch_manager(monkeypatch, send_touch_event=lambda *args: calls.append(args))
    event = TouchEvent(action=2, x=1, y=2, w=100, h=200)
    assert ds_router.send_touch("SER-9", event) == {"status": "ok"}
    assert calls == [("SER-9", 2, 1, 2, 100, 200)]


def test_send_touch_endpoint_maps_manager_errors(monkeypatch):
    def invalid(*_args):
        raise ValueError("设备未连接")

    _patch_manager(monkeypatch, send_touch_event=invalid)
    with pytest.raises(HTTPException) as bad_request:
        ds_router.send_touch("SER-9", TouchEvent(x=0, y=0))
    assert bad_request.value.status_code == 400
    assert bad_request.value.detail == "设备未连接"

    def broken(*_args):
        raise RuntimeError("control socket closed")

    _patch_manager(monkeypatch, send_touch_event=broken)
    with pytest.raises(HTTPException) as failure:
        ds_router.send_touch("SER-9", TouchEvent(x=0, y=0))
    assert failure.value.status_code == 500


def test_reconnect_scrcpy_triggers_stream_setup(monkeypatch):
    ensured = []
    _patch_manager(monkeypatch, ensure_device_stream=ensured.append)
    assert ds_router.reconnect_scrcpy("SER-9") == {"status": "ok", "serial": "SER-9"}
    assert ensured == ["SER-9"]
