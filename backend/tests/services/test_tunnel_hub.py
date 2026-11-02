"""TunnelHub 远程接入隧道单元测试（覆盖率补口：此前该模块约 20% 覆盖率）。

覆盖策略：
- 纯逻辑（_LinkRateWindow、allocate_conn_id、_pick_free_port、desired_ports、链路快照）直接调用；
- AgentSession 发送管线用假 WebSocket + 闸门事件精确控制时序，覆盖背压等待、分片发送、
  异常关停等分支，不触真实网络；
- 隧道 TCP 一侧用 asyncio.StreamReader + 假 writer 驱动 _handle_tunnel_client /
  _drain_tunnel_connection；
- 持久化路径（_persist_* / list_agents / startup_reset / _touch_last_seen）用 sqlite
  （SQLAlchemy 同步 engine）真实落库，只 monkeypatch tunnel_hub.engine；
- 端口监听：仅一条成功路径真实绑定临时空闲端口，其余通过模块级 asyncio 代理替换
  start_server，避免占用 28100+ 的真实端口。

注意：`import app.device_agents.tunnel_hub as x` 会被包 __init__ 重导出的单例遮蔽，
必须用 importlib.import_module 拿到模块本体。
"""

import asyncio
import importlib
import json
import socket
import time
from collections import deque
from datetime import datetime

import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session
from starlette.websockets import WebSocketDisconnect

from app.models.base import Base
from app.models.bootstrap import load_all_models
from app.models.device import Device, DeviceStatus
from app.models.device_agent import RemoteAgent, RemoteAgentDevice

load_all_models()

th = importlib.import_module("app.device_agents.tunnel_hub")
HUB = th.tunnel_hub


# ==================== 假对象与工具 ====================


class _FakeWebSocket:
    """替代 starlette WebSocket：只需 receive/send_text/send_bytes/close 四个接口。"""

    def __init__(self):
        self.inbox: asyncio.Queue = asyncio.Queue()
        self.sent_text: list[str] = []
        self.sent_bytes: list[bytes] = []
        self.close_codes: list[int] = []
        self.closed = False
        self.fail_text = False
        self.fail_bytes = False
        self.fail_close = False
        self.block_bytes: asyncio.Event | None = None  # 发送 binary 前的闸门
        self.blocked = asyncio.Event()  # 标记 sender 已被闸门卡住
        self.raise_after_inbox_empty: BaseException | None = None

    def push(self, message: dict) -> None:
        self.inbox.put_nowait(message)

    async def receive(self) -> dict:
        if self.raise_after_inbox_empty is not None and self.inbox.empty():
            raise self.raise_after_inbox_empty
        return await self.inbox.get()

    async def send_text(self, text: str) -> None:
        if self.fail_text:
            raise RuntimeError("ws send_text failed")
        self.sent_text.append(text)

    async def send_bytes(self, data: bytes) -> None:
        if self.block_bytes is not None:
            self.blocked.set()
            await self.block_bytes.wait()
            self.blocked.clear()
        if self.fail_bytes:
            raise RuntimeError("ws send_bytes failed")
        self.sent_bytes.append(data)

    async def close(self, code: int = 1000, reason: str | None = None) -> None:
        self.close_codes.append(code)
        if self.fail_close:
            raise RuntimeError("ws close failed")
        self.closed = True


class _FakeStreamReader:
    """替代 asyncio.StreamReader：默认值断言不驱动读取，构造不依赖 current event loop。"""


class _FakeStreamWriter:
    """替代 asyncio.StreamWriter：tunnel_hub 只用到 write/drain/close/get_extra_info。"""

    def __init__(self, sock=None, extra_error: bool = False):
        self.writes: list[bytes] = []
        self.drain_calls = 0
        self.closed = False
        self.drain_error: BaseException | None = None
        self.close_error: BaseException | None = None
        self.extra: dict = {}
        self.extra_error = extra_error
        if sock is not None:
            self.extra["socket"] = sock

    def get_extra_info(self, name, default=None):
        if self.extra_error:
            raise RuntimeError("no extra info")
        return self.extra.get(name, default)

    def write(self, data: bytes) -> None:
        self.writes.append(bytes(data))

    async def drain(self) -> None:
        self.drain_calls += 1
        if self.drain_error is not None:
            raise self.drain_error

    def close(self) -> None:
        self.closed = True
        if self.close_error is not None:
            raise self.close_error

    async def wait_closed(self) -> None:
        pass


class _FakeSock:
    """替代 socket 对象：记录 setsockopt 调用，可注入失败。"""

    def __init__(self, fail: bool = False):
        self.calls: list[tuple] = []
        self.fail = fail

    def setsockopt(self, level, optname, value):
        if self.fail:
            raise OSError("setsockopt failed")
        self.calls.append((level, optname, value))


class _FakeServer:
    """替代 asyncio.Server：记录 close/wait_closed，可注入 wait_closed 异常。"""

    def __init__(self):
        self.closed = False
        self.wait_closed_error: BaseException | None = None
        self.handler = None

    def close(self) -> None:
        self.closed = True

    async def wait_closed(self) -> None:
        if self.wait_closed_error is not None:
            raise self.wait_closed_error


class _KeeperRecorder:
    """记录 trigger 调用次数的假 adb keeper。"""

    def __init__(self):
        self.count = 0

    def trigger(self) -> None:
        self.count += 1


class _AsyncioProxy:
    """让 tunnel_hub 模块内的 asyncio 引用走代理：仅替换个别属性，其余转发真实模块。"""

    def __init__(self, **overrides):
        self._overrides = overrides

    def __getattr__(self, name):
        if name in self._overrides:
            return self._overrides[name]
        return getattr(asyncio, name)


class _FrozenTime:
    """仅替换 time.time 的代理，monotonic 等其余属性转发真实 time 模块。"""

    def __init__(self, now: float):
        self.now = now

    def time(self) -> float:
        return self.now

    def __getattr__(self, name):
        return getattr(time, name)


def _patch_fake_start_server(monkeypatch, error: BaseException | None = None) -> list[_FakeServer]:
    """把 tunnel_hub 模块内的 asyncio.start_server 换成返回假 Server 的桩。"""
    servers: list[_FakeServer] = []

    async def _fake_start_server(handler, host=None, port=None, **kwargs):
        if error is not None:
            raise error
        server = _FakeServer()
        server.handler = handler
        servers.append(server)
        return server

    monkeypatch.setattr(th, "asyncio", _AsyncioProxy(start_server=_fake_start_server))
    return servers


async def _wait_until(predicate, timeout: float = 2.0) -> None:
    """等待条件成立（轮询 5ms），超时直接失败，避免测试挂起。"""
    deadline = time.monotonic() + timeout
    while not predicate():
        if time.monotonic() > deadline:
            raise AssertionError("等待条件超时")
        await asyncio.sleep(0.005)


def _raising_session(*_args, **_kwargs):
    raise RuntimeError("db unavailable")


def _new_agent_session(name: str = "agent-a", agent_id: int = 1, ws: _FakeWebSocket | None = None):
    return th.AgentSession(HUB, ws if ws is not None else _FakeWebSocket(), name, agent_id)


def _make_runtime(usb_serial: str, port: int, listener=None, error: str | None = None, meta: dict | None = None):
    runtime = th.RemoteDeviceRuntime(usb_serial, port, meta or {})
    runtime.listener = listener
    runtime.error = error
    return runtime


def _make_conn(conn_id: int, usb_serial: str = "usb-1", reader=None, writer=None):
    return th.TunnelConnection(
        conn_id,
        usb_serial,
        reader if reader is not None else asyncio.StreamReader(),
        writer if writer is not None else _FakeStreamWriter(),
    )


def _register_message(name: str = "agent-a", protocol: int = 1, devices: list | None = None) -> dict:
    return {
        "type": "websocket.receive",
        "text": json.dumps(
            {
                "type": "register",
                "protocol": protocol,
                "agent": {"name": name, "version": "1.0", "os": "Linux"},
                "devices": devices or [],
            }
        ),
    }


def _free_tcp_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


# ==================== 夹具 ====================


@pytest.fixture(autouse=True)
def _clean_hub_state():
    """每个用例前后清理全局单例状态（会话表/锁/keeper），保证可单文件独立运行。"""
    HUB._sessions.clear()
    HUB._lock = asyncio.Lock()
    HUB.set_keeper(None)
    yield
    HUB._sessions.clear()
    HUB._lock = asyncio.Lock()
    HUB.set_keeper(None)


@pytest.fixture()
def db_engine(tmp_path, monkeypatch):
    """用 sqlite 真实落库替换 tunnel_hub.engine，覆盖持久化逻辑。"""
    engine_ = create_engine(
        f"sqlite:///{tmp_path / 'tunnel_hub.sqlite3'}",
        connect_args={"check_same_thread": False},
    )
    Base.metadata.create_all(engine_)
    monkeypatch.setattr(th, "engine", engine_)
    yield engine_
    engine_.dispose()


# ==================== _LinkRateWindow 与运行时对象 ====================


def test_link_rate_window_accumulates_same_second_and_evicts(monkeypatch):
    clock = _FrozenTime(1000.0)
    monkeypatch.setattr(th, "time", clock)
    window = th._LinkRateWindow(window_seconds=10)
    assert window.rate_bps() == 0

    window.record(80)
    window.record(20)
    assert list(window._buckets) == [(1000, 100)]  # 同秒合并
    assert window.rate_bps() == 80  # 100*8/10

    clock.now = 1015.0
    window.record(50)
    assert (1000, 100) not in window._buckets  # 过期桶淘汰
    assert window.rate_bps() == 40  # 50*8/10


def test_link_rate_window_excludes_bucket_on_cutoff(monkeypatch):
    clock = _FrozenTime(2000.0)
    monkeypatch.setattr(th, "time", clock)
    window = th._LinkRateWindow(window_seconds=10)
    window.record(10)
    clock.now = 2010.0
    assert window.rate_bps() == 0  # second <= cutoff 的桶不计入
    window.record(90)
    assert list(window._buckets) == [(2010, 90)]
    assert window.rate_bps() == 72


def test_tunnel_connection_defaults():
    writer = _FakeStreamWriter()
    # 直接构造 asyncio.StreamReader 依赖线程 current event loop；全量运行时
    # 前面的 asyncio.run 会把它置空。默认值断言不读取数据，改用替身构造。
    conn = th.TunnelConnection(7, "usb-1", _FakeStreamReader(), writer)
    assert conn.conn_id == 7 and conn.usb_serial == "usb-1"
    assert conn.closed is False and conn.pump_task is None and conn.writer_task is None
    assert conn.write_queue.maxsize == th.TUNNEL_CONNECTION_MAX_INBOUND_CHUNKS


def test_remote_device_runtime_ready_flag():
    meta = {"model": "P"}
    runtime = th.RemoteDeviceRuntime("usb-1", 28100, meta)
    assert runtime.meta == {"model": "P"} and runtime.meta is not meta
    assert runtime.ready is False and runtime.error is None
    runtime.listener = _FakeServer()
    assert runtime.ready is True
    runtime.error = "boom"
    assert runtime.ready is False


def test_allocate_conn_id_increments_and_wraps_at_31_bits():
    session = _new_agent_session()
    assert session.allocate_conn_id() == 1
    assert session.allocate_conn_id() == 2
    session._next_conn_id = 0x7FFFFFFF
    assert session.allocate_conn_id() == 0x7FFFFFFF
    assert session._next_conn_id == 1
    assert session.allocate_conn_id() == 1


# ==================== AgentSession 发送管线 ====================


@pytest.mark.asyncio
async def test_send_control_delivers_json_and_records_outbound_rate():
    ws = _FakeWebSocket()
    session = _new_agent_session(ws=ws)
    await session.send_control({"type": "hello", "n": 1})
    assert json.loads(ws.sent_text[0]) == {"type": "hello", "n": 1}
    assert session.outbound_rate.rate_bps() > 0
    await session.shutdown_sender()


@pytest.mark.asyncio
async def test_send_control_rejects_closed_session():
    session = _new_agent_session()
    session.closed = True
    with pytest.raises(ConnectionError):
        await session.send_control({"type": "x"})
    assert session._sender_task is None


@pytest.mark.asyncio
async def test_send_control_failure_propagates_and_shuts_down_session():
    ws = _FakeWebSocket()
    ws.fail_text = True
    session = _new_agent_session(ws=ws)
    with pytest.raises(RuntimeError):
        await session.send_control({"type": "x"})
    await _wait_until(lambda: ws.closed)
    assert session.closed is True
    assert session._sender_task is None


@pytest.mark.asyncio
async def test_send_data_rejects_closed_session():
    session = _new_agent_session()
    session.closed = True
    with pytest.raises(ConnectionError):
        await session.send_data(1, b"x")


@pytest.mark.asyncio
async def test_send_data_after_discard_is_silently_dropped():
    ws = _FakeWebSocket()
    session = _new_agent_session(ws=ws)
    await session.discard_connection_data(4)
    await session.send_data(4, b"late")
    await asyncio.sleep(0)
    assert ws.sent_bytes == []
    assert 4 not in session._data_pending_bytes


@pytest.mark.asyncio
async def test_discard_connection_data_clears_queues_and_marks_closed():
    session = _new_agent_session()
    session._data_queues[5] = deque([b"a"])
    session._data_pending_bytes[5] = 1
    await session.discard_connection_data(5)
    assert 5 in session._closed_connections
    assert 5 not in session._data_queues and 5 not in session._data_pending_bytes
    await session.discard_connection_data(99)  # 缺失键不抛错
    assert 99 in session._closed_connections


@pytest.mark.asyncio
async def test_send_data_splits_oversized_chunks_round_robin(monkeypatch):
    monkeypatch.setattr(th, "TUNNEL_SEND_CHUNK_BYTES", 4)
    ws = _FakeWebSocket()
    session = _new_agent_session(ws=ws)
    await session.send_data(7, b"0123456789")
    await _wait_until(lambda: len(ws.sent_bytes) == 3)
    assert [th.decode_data_frame(f) for f in ws.sent_bytes] == [
        (7, b"0123"),
        (7, b"4567"),
        (7, b"89"),
    ]
    assert 7 not in session._data_pending_bytes and 7 not in session._data_queues
    await session.shutdown_sender()


@pytest.mark.asyncio
async def test_send_data_waits_for_backpressure_release(monkeypatch):
    monkeypatch.setattr(th, "TUNNEL_CONNECTION_MAX_PENDING_BYTES", 4)
    ws = _FakeWebSocket()
    ws.block_bytes = asyncio.Event()
    session = _new_agent_session(ws=ws)
    await session.send_data(7, b"AAAA")
    await ws.blocked.wait()  # sender 已被闸门卡在首个帧上
    await session.send_data(7, b"BBBB")

    third = asyncio.create_task(session.send_data(7, b"CCCC"))
    await asyncio.sleep(0.01)
    assert not third.done()  # 背压未释放前必须等待

    ws.block_bytes.set()
    await asyncio.wait_for(third, timeout=2)
    await _wait_until(lambda: len(ws.sent_bytes) == 3)
    payload = b"".join(th.decode_data_frame(f)[1] for f in ws.sent_bytes)
    assert payload == b"AAAABBBBCCCC"
    assert 7 not in session._data_pending_bytes
    await session.shutdown_sender()


@pytest.mark.asyncio
async def test_send_data_queues_second_chunk_without_duplicate_round_robin(monkeypatch):
    """队列非空时第二次入队不再重复登记 round_robin（send_data 的假分支）。"""
    monkeypatch.setattr(th, "TUNNEL_CONNECTION_MAX_PENDING_BYTES", 8)
    ws = _FakeWebSocket()
    ws.block_bytes = asyncio.Event()
    session = _new_agent_session(ws=ws)
    await session.send_data(7, b"AAAA")
    await ws.blocked.wait()  # sender 已弹出首帧并卡在 send_bytes
    await session.send_data(7, b"BBBB")
    await session.send_data(7, b"CCCC")  # 此时队列里已有 B，走队列非空分支

    ws.block_bytes.set()
    await _wait_until(lambda: len(ws.sent_bytes) == 3)
    payload = b"".join(th.decode_data_frame(f)[1] for f in ws.sent_bytes)
    assert payload == b"AAAABBBBCCCC"
    assert 7 not in session._data_pending_bytes
    await session.shutdown_sender()


@pytest.mark.asyncio
async def test_send_data_returns_when_connection_closed_while_waiting(monkeypatch):
    monkeypatch.setattr(th, "TUNNEL_CONNECTION_MAX_PENDING_BYTES", 4)
    ws = _FakeWebSocket()
    ws.block_bytes = asyncio.Event()
    session = _new_agent_session(ws=ws)
    await session.send_data(7, b"AAAA")
    await ws.blocked.wait()
    await session.send_data(7, b"BBBB")

    third = asyncio.create_task(session.send_data(7, b"CCCC"))
    await asyncio.sleep(0.01)
    assert not third.done()
    await session.discard_connection_data(7)
    await asyncio.wait_for(third, timeout=2)  # 连接被丢弃 → 直接返回，不发送

    ws.block_bytes.set()
    await _wait_until(lambda: ws.sent_bytes)
    assert all(th.decode_data_frame(f)[1] != b"CCCC" for f in ws.sent_bytes)
    await session.shutdown_sender()


@pytest.mark.asyncio
async def test_send_data_returns_when_session_closed_while_waiting(monkeypatch):
    monkeypatch.setattr(th, "TUNNEL_CONNECTION_MAX_PENDING_BYTES", 4)
    ws = _FakeWebSocket()
    ws.block_bytes = asyncio.Event()
    session = _new_agent_session(ws=ws)
    await session.send_data(7, b"AAAA")
    await ws.blocked.wait()
    await session.send_data(7, b"BBBB")

    waiter = asyncio.create_task(session.send_data(7, b"CCCC"))
    await asyncio.sleep(0.01)
    assert not waiter.done()
    await session.shutdown_sender()
    await asyncio.wait_for(waiter, timeout=2)  # 会话关闭 → 直接返回
    assert session.closed is True


@pytest.mark.asyncio
async def test_send_data_binary_send_failure_shuts_session_down():
    ws = _FakeWebSocket()
    ws.fail_bytes = True
    session = _new_agent_session(ws=ws)
    await session.send_data(1, b"abc")
    await _wait_until(lambda: ws.closed)
    assert session.closed is True


@pytest.mark.asyncio
async def test_sender_failure_swallows_websocket_close_error():
    """发送失败后 websocket.close 再抛错也必须被吞掉。"""
    ws = _FakeWebSocket()
    ws.fail_bytes = True
    ws.fail_close = True
    session = _new_agent_session(ws=ws)
    await session.send_data(1, b"abc")
    await _wait_until(lambda: session.closed)
    assert session.closed is True and ws.closed is False
    assert ws.close_codes == [1000]


@pytest.mark.asyncio
async def test_sender_loop_skips_stale_round_robin_entry():
    ws = _FakeWebSocket()
    session = _new_agent_session(ws=ws)
    async with session._send_condition:
        session._round_robin_connections.append(99)  # 没有对应数据队列的陈旧条目
        session._ensure_sender_locked()
        session._send_condition.notify_all()
    await session.send_data(1, b"ok")
    await _wait_until(lambda: ws.sent_bytes)
    assert th.decode_data_frame(ws.sent_bytes[0]) == (1, b"ok")
    await session.shutdown_sender()


@pytest.mark.asyncio
async def test_sender_loop_exits_immediately_when_session_closed():
    session = _new_agent_session()
    session.closed = True
    session._ensure_sender_locked()
    sender = session._sender_task
    assert sender is not None
    await asyncio.wait_for(sender, timeout=2)
    assert sender.done() and not sender.cancelled()


@pytest.mark.asyncio
async def test_shutdown_sender_fails_pending_control_and_clears_state():
    session = _new_agent_session()
    loop = asyncio.get_running_loop()
    pending = loop.create_future()
    done = loop.create_future()
    done.set_result(None)
    session._control_queue.append(('{"type": "a"}', pending))
    session._control_queue.append(('{"type": "b"}', done))
    session._data_queues[3] = deque([b"x"])
    session._data_pending_bytes[3] = 1
    session._round_robin_connections.append(3)

    await session.shutdown_sender()

    assert session.closed is True
    with pytest.raises(ConnectionError):
        await pending
    assert done.result() is None  # 已完成的 future 不再被改写
    assert session._data_queues == {} and session._data_pending_bytes == {}
    assert not session._round_robin_connections
    assert session._sender_task is None


@pytest.mark.asyncio
async def test_shutdown_sender_cancels_blocked_sender_task():
    ws = _FakeWebSocket()
    ws.block_bytes = asyncio.Event()
    session = _new_agent_session(ws=ws)
    await session.send_data(1, b"blocked-data")
    await ws.blocked.wait()  # sender 停在 send_bytes 上
    await session.shutdown_sender()
    assert session.closed is True and session._sender_task is None
    assert ws.sent_bytes == []  # 卡住的那一帧没有发出去


# ==================== TunnelHub 同步工具 ====================


def test_pick_free_port_picks_first_free_or_none(monkeypatch):
    monkeypatch.setattr(th, "TUNNEL_PORT_RANGE_START", 10)
    monkeypatch.setattr(th, "TUNNEL_PORT_RANGE_END", 12)
    assert HUB._pick_free_port({10, 12}) == 11
    assert HUB._pick_free_port({10, 11, 12}) is None


def test_desired_ports_only_includes_ready_devices():
    session = _new_agent_session(name="agent-a")
    session.devices["usb-1"] = _make_runtime("usb-1", 28100, listener=_FakeServer())
    session.devices["usb-2"] = _make_runtime("usb-2", 28101, error="boom")
    session.devices["usb-3"] = _make_runtime("usb-3", 28102)
    HUB._sessions["agent-a"] = session
    assert HUB.desired_ports() == {28100}
    HUB._sessions.clear()
    assert HUB.desired_ports() == set()


def test_is_agent_online_and_notify_keeper():
    session = _new_agent_session(name="agent-a")
    HUB._sessions["agent-a"] = session
    assert HUB.is_agent_online("agent-a") is True
    assert HUB.is_agent_online("agent-b") is False

    HUB._notify_keeper()  # keeper 为空 → 无操作
    keeper = _KeeperRecorder()
    HUB.set_keeper(keeper)
    HUB._notify_keeper()
    assert keeper.count == 1

    class _BoomKeeper:
        def trigger(self):
            raise RuntimeError("keeper down")

    HUB.set_keeper(_BoomKeeper())
    HUB._notify_keeper()  # keeper 异常被吞掉


def test_link_quality_snapshot_none_closed_and_values():
    assert HUB._link_quality_snapshot(None) is None

    session = _new_agent_session()
    session.closed = True
    assert HUB._link_quality_snapshot(session) is None

    session.closed = False
    session.link_rtt_ms = 20.0
    session.link_rtt_samples.extend([10.0, 20.0])
    session.inbound_rate.record(1000)
    session.outbound_rate.record(500)
    snap = HUB._link_quality_snapshot(session)
    assert snap["rtt_ms"] == 20.0 and snap["rtt_avg_ms"] == 15.0
    assert snap["up_bps"] == 800 and snap["down_bps"] == 400
    assert snap["bandwidth_probe"] is None


# ==================== sqlite 持久化 ====================


def test_startup_reset_marks_agents_and_tunnel_devices_offline(db_engine):
    with Session(db_engine) as db:
        db.add_all(
            [
                RemoteAgent(name="live-agent", status="ONLINE"),
                RemoteAgent(name="already-offline", status="OFFLINE"),
                Device(serial="127.0.0.1:28100", ip_address="127.0.0.1", status=DeviceStatus.online),
                Device(serial="emulator-5554", ip_address="127.0.0.1", status=DeviceStatus.online),
                Device(serial="127.0.0.1:28101", ip_address="10.0.0.5", status=DeviceStatus.online),
            ]
        )
        db.commit()

    HUB.startup_reset()

    with Session(db_engine) as db:
        live = db.scalars(select(RemoteAgent).where(RemoteAgent.name == "live-agent")).one()
        assert live.status == "OFFLINE" and live.updated_at is not None
        tunnel_dev = db.scalars(select(Device).where(Device.serial == "127.0.0.1:28100")).one()
        assert tunnel_dev.status == DeviceStatus.offline and tunnel_dev.last_seen_at is not None
        emulator = db.scalars(select(Device).where(Device.serial == "emulator-5554")).one()
        assert emulator.status == DeviceStatus.online
        non_local = db.scalars(select(Device).where(Device.serial == "127.0.0.1:28101")).one()
        assert non_local.status == DeviceStatus.online


def test_startup_reset_swallows_db_errors(monkeypatch):
    monkeypatch.setattr(th, "Session", _raising_session)
    HUB.startup_reset()  # 不抛异常


def test_persist_agent_online_creates_and_updates_rows(db_engine):
    agent_id = HUB._persist_agent_online("agent-a", {"version": "1.2.3", "os": "Windows 11"}, "admin")
    with Session(db_engine) as db:
        agent = db.get(RemoteAgent, agent_id)
        assert agent.status == "ONLINE"
        assert agent.agent_version == "1.2.3" and agent.os_info == "Windows 11"
        assert agent.last_seen_at is not None

    again = HUB._persist_agent_online("agent-a", {"version": "2.0", "os": ""}, "admin")
    assert again == agent_id
    with Session(db_engine) as db:
        agent = db.get(RemoteAgent, agent_id)
        assert agent.agent_version == "2.0" and agent.os_info == "Windows 11"  # 空 os 保留旧值

    long_id = HUB._persist_agent_online("agent-long", {"version": "", "os": "y" * 200}, "admin")
    with Session(db_engine) as db:
        agent = db.get(RemoteAgent, long_id)
        assert agent.os_info == "y" * 120 and agent.agent_version is None


def test_persist_agent_offline_updates_agent_and_devices(db_engine):
    agent_id = HUB._persist_agent_online("agent-a", {}, "admin")
    empty_id = HUB._persist_agent_online("agent-empty", {}, "admin")  # 无设备映射
    port_map, _ = HUB._persist_device_mappings(agent_id, {"usb-1": {"model": "M"}})
    serial = th.tunnel_serial(port_map["usb-1"])

    HUB._persist_agent_offline(empty_id)  # serials 为空的分支
    HUB._persist_agent_offline(agent_id)

    with Session(db_engine) as db:
        assert db.get(RemoteAgent, agent_id).status == "OFFLINE"
        assert db.get(RemoteAgent, empty_id).status == "OFFLINE"
        dev = db.scalars(select(Device).where(Device.serial == serial)).one()
        assert dev.status == DeviceStatus.offline and dev.last_seen_at is not None

    HUB._persist_agent_offline(999999)  # 不存在的 agent → 安全返回


def test_persist_agent_offline_swallows_db_errors(monkeypatch):
    monkeypatch.setattr(th, "Session", _raising_session)
    HUB._persist_agent_offline(1)  # 不抛异常


def test_persist_device_mappings_creates_mapping_and_device_rows(db_engine):
    reported = {
        "usb-1": {"model": "Pixel 8", "brand": "Google", "os_version": "14"},
        "usb-2": {"model": "Mi 14", "brand": "Xiaomi"},
    }
    port_map, errors = HUB._persist_device_mappings(1, reported)
    assert errors == {}
    assert port_map == {"usb-1": 28100, "usb-2": 28101}
    with Session(db_engine) as db:
        rows = db.scalars(select(RemoteAgentDevice).order_by(RemoteAgentDevice.tunnel_port)).all()
        assert [(r.usb_serial, r.tunnel_port) for r in rows] == [("usb-1", 28100), ("usb-2", 28101)]
        assert rows[0].last_seen_at is not None
        dev1 = db.scalars(select(Device).where(Device.serial == "127.0.0.1:28100")).one()
        assert dev1.name == "Google Pixel 8 (usb-1)"
        assert dev1.status == DeviceStatus.online
        assert dev1.ip_address == "127.0.0.1" and dev1.os_version == "14"


def test_persist_device_mappings_updates_existing_rows_and_fills_names(db_engine):
    with Session(db_engine) as db:
        db.add(
            RemoteAgentDevice(
                agent_id=3, usb_serial="usb-5", tunnel_port=28105, model="Old", brand="Old", os_version="9"
            )
        )
        db.add(Device(serial="127.0.0.1:28105", name="Handset", ip_address="127.0.0.1", status=DeviceStatus.offline))
        db.commit()

    port_map, errors = HUB._persist_device_mappings(
        3, {"usb-5": {"model": "New", "brand": "BrandX", "os_version": "15"}}
    )
    assert port_map == {"usb-5": 28105} and errors == {}
    with Session(db_engine) as db:
        mapping = db.scalars(select(RemoteAgentDevice)).one()
        assert mapping.model == "New" and mapping.brand == "BrandX" and mapping.os_version == "15"
        dev = db.scalars(select(Device)).one()
        assert dev.name == "Handset"  # 已有名称不被覆盖
        assert dev.model == "New" and dev.status == DeviceStatus.online and dev.last_seen_at is not None

    with Session(db_engine) as db:  # 设备名称为空时用上报信息补齐
        dev = db.scalars(select(Device)).one()
        dev.name = None
        db.add(dev)
        db.commit()

    HUB._persist_device_mappings(3, {"usb-5": {"model": "New2", "brand": "BrandY"}})
    with Session(db_engine) as db:
        dev = db.scalars(select(Device)).one()
        assert dev.name == "BrandY New2 (usb-5)" and dev.model == "New2"
        assert len(db.scalars(select(RemoteAgentDevice)).all()) == 1  # 既有映射不重复创建


def test_persist_device_mappings_port_exhaustion(db_engine, monkeypatch):
    monkeypatch.setattr(th, "TUNNEL_PORT_RANGE_START", 28150)
    monkeypatch.setattr(th, "TUNNEL_PORT_RANGE_END", 28150)
    with Session(db_engine) as db:
        db.add(RemoteAgentDevice(agent_id=2, usb_serial="existing", tunnel_port=28150))
        db.commit()

    port_map, errors = HUB._persist_device_mappings(2, {"usb-1": {"model": "M"}})
    assert port_map == {}
    assert "28150-28150" in errors["usb-1"] and "耗尽" in errors["usb-1"]
    with Session(db_engine) as db:
        assert len(db.scalars(select(RemoteAgentDevice)).all()) == 1


def test_touch_last_seen_writes_only_after_interval(db_engine):
    agent_id = HUB._persist_agent_online("agent-a", {}, "admin")
    session = _new_agent_session(name="agent-a", agent_id=agent_id)

    with Session(db_engine) as db:
        agent = db.get(RemoteAgent, agent_id)
        agent.last_seen_at = datetime(2020, 1, 1)
        db.add(agent)
        db.commit()

    session._last_seen_written = 0.0  # 远超间隔 → 触发写入
    HUB._touch_last_seen(session)
    with Session(db_engine) as db:
        assert db.get(RemoteAgent, agent_id).last_seen_at.year > 2020

    with Session(db_engine) as db:
        agent = db.get(RemoteAgent, agent_id)
        agent.last_seen_at = datetime(2020, 1, 1)
        db.add(agent)
        db.commit()

    session._last_seen_written = time.monotonic()  # 间隔内 → 跳过
    HUB._touch_last_seen(session)
    with Session(db_engine) as db:
        assert db.get(RemoteAgent, agent_id).last_seen_at.year == 2020


def test_touch_last_seen_missing_agent_is_noop(db_engine):
    session = _new_agent_session(agent_id=12345)
    session._last_seen_written = 0.0
    HUB._touch_last_seen(session)  # 库中无该 agent → 直接返回


def test_touch_last_seen_swallows_db_errors(monkeypatch):
    monkeypatch.setattr(th, "Session", _raising_session)
    session = _new_agent_session(agent_id=1)
    session._last_seen_written = 0.0
    HUB._touch_last_seen(session)  # 不抛异常


def test_list_agents_merges_db_rows_and_live_runtime(db_engine):
    with Session(db_engine) as db:
        agent_a = RemoteAgent(name="agent-a", status="OFFLINE", agent_version="1.0")
        agent_b = RemoteAgent(name="agent-b", status="OFFLINE")
        db.add_all([agent_a, agent_b])
        db.commit()
        db.refresh(agent_a)
        db.refresh(agent_b)
        agent_a_id, agent_b_id = agent_a.id, agent_b.id
        db.add_all(
            [
                RemoteAgentDevice(
                    agent_id=agent_a_id,
                    usb_serial="usb-1",
                    tunnel_port=28100,
                    model="P",
                    brand="G",
                    os_version="14",
                ),
                RemoteAgentDevice(agent_id=agent_a_id, usb_serial="usb-2", tunnel_port=28101),
                RemoteAgentDevice(agent_id=agent_b_id, usb_serial="usb-3", tunnel_port=28102),
            ]
        )
        db.commit()

    session = _new_agent_session(name="agent-a", agent_id=agent_a_id)
    session.devices["usb-1"] = _make_runtime("usb-1", 28100, listener=_FakeServer())
    session.devices["usb-2"] = _make_runtime("usb-2", 28101, error="监听失败")
    session.devices["usb-9"] = _make_runtime("usb-9", 28109, meta={"model": "X", "brand": "Y", "os_version": "13"})
    HUB._sessions["agent-a"] = session

    items = HUB.list_agents()
    by_name = {item["name"]: item for item in items}

    a = by_name["agent-a"]
    assert a["status"] == "ONLINE" and a["device_count"] == 3 and a["online_device_count"] == 1
    assert a["link_quality"] is not None and a["link_quality"]["rtt_ms"] is None
    devices = {d["usb_serial"]: d for d in a["devices"]}
    assert devices["usb-1"]["online"] is True and devices["usb-1"]["serial"] == "127.0.0.1:28100"
    assert devices["usb-2"]["online"] is False and devices["usb-2"]["error"] == "监听失败"
    assert devices["usb-2"]["last_seen_at"] is None
    assert devices["usb-9"]["tunnel_port"] == 28109 and devices["usb-9"]["last_seen_at"] is None
    assert devices["usb-9"]["model"] == "X" and devices["usb-9"]["online"] is False

    b = by_name["agent-b"]
    assert b["status"] == "OFFLINE" and b["link_quality"] is None
    assert b["devices"][0]["usb_serial"] == "usb-3" and b["devices"][0]["serial"] == "127.0.0.1:28102"
    assert b["agent_version"] is None and b["created_at"] is not None


def test_list_agents_swallows_db_errors(monkeypatch):
    monkeypatch.setattr(th, "Session", _raising_session)
    assert HUB.list_agents() == []


# ==================== 带宽探测 ====================


@pytest.mark.asyncio
async def test_probe_agent_bandwidth_success_measures_and_stores():
    ws = _FakeWebSocket()
    session = _new_agent_session(ws=ws, agent_id=7)
    session.link_rtt_ms = 25.0
    HUB._sessions["agent-a"] = session

    task = asyncio.create_task(HUB.probe_agent_bandwidth(7, size_bytes=4096, timeout=1.0))
    await _wait_until(lambda: ws.sent_text)
    probe = json.loads(ws.sent_text[0])
    assert probe["type"] == "bandwidth_probe" and probe["size"] == 4096

    await HUB._on_control(
        session, {"type": "bandwidth_probe_result", "probe_id": probe["probe_id"], "payload": "x" * 2048}
    )
    result = await asyncio.wait_for(task, timeout=2)
    assert result["bytes"] == 2048 and result["rtt_ms_at_probe"] == 25.0
    assert result["bps"] > 0 and result["elapsed_ms"] >= 0 and result["at"]
    assert session.bandwidth_probe == result
    assert session._probe_futures == {}
    await session.shutdown_sender()


@pytest.mark.asyncio
async def test_probe_agent_bandwidth_timeout_cleans_future():
    ws = _FakeWebSocket()
    session = _new_agent_session(ws=ws, agent_id=7)
    HUB._sessions["agent-a"] = session
    with pytest.raises(TimeoutError):
        await HUB.probe_agent_bandwidth(7, size_bytes=16, timeout=0.05)
    assert session._probe_futures == {}
    await session.shutdown_sender()


@pytest.mark.asyncio
async def test_probe_agent_bandwidth_rejects_offline_or_closed():
    with pytest.raises(ValueError):
        await HUB.probe_agent_bandwidth(99)

    session = _new_agent_session(agent_id=99)
    session.closed = True
    HUB._sessions["agent-a"] = session
    with pytest.raises(ValueError):
        await HUB.probe_agent_bandwidth(99)


# ==================== 控制消息与数据帧 ====================


@pytest.mark.asyncio
async def test_on_control_ping_updates_rtt_and_answers():
    ws = _FakeWebSocket()
    session = _new_agent_session(ws=ws)
    await HUB._on_control(session, {"type": "ping", "rtt_ms": 12.5})
    assert session.link_rtt_ms == 12.5 and list(session.link_rtt_samples) == [12.5]

    for bad in ("abc", -1, 60_000, None):  # 非法 rtt 被忽略
        await HUB._on_control(session, {"type": "ping", "rtt_ms": bad})
    assert session.link_rtt_ms == 12.5
    assert [json.loads(t)["type"] for t in ws.sent_text] == ["pong"] * 5
    await session.shutdown_sender()


@pytest.mark.asyncio
async def test_on_control_ping_send_failure_is_swallowed():
    ws = _FakeWebSocket()
    ws.fail_text = True
    session = _new_agent_session(ws=ws)
    await HUB._on_control(session, {"type": "ping", "rtt_ms": 5})  # 不抛异常
    await _wait_until(lambda: session.closed)
    await _wait_until(lambda: ws.closed)


@pytest.mark.asyncio
async def test_on_control_bandwidth_probe_result_branches():
    session = _new_agent_session()
    await HUB._on_control(session, {"type": "bandwidth_probe_result", "probe_id": 42, "payload": "xy"})

    loop = asyncio.get_running_loop()
    done = loop.create_future()
    done.set_result("keep")
    session._probe_futures[7] = done
    await HUB._on_control(session, {"type": "bandwidth_probe_result", "probe_id": 7, "payload": "abc"})
    assert done.result() == "keep"  # 已完成的 future 不被改写


@pytest.mark.asyncio
async def test_on_control_devices_update_applies_and_notifies(db_engine, monkeypatch):
    _patch_fake_start_server(monkeypatch)
    ws = _FakeWebSocket()
    session = _new_agent_session(ws=ws, agent_id=1)
    keeper = _KeeperRecorder()
    HUB.set_keeper(keeper)

    await HUB._on_control(session, {"type": "devices", "devices": [{"usb_serial": "usb-1", "model": "M"}]})

    reply = json.loads(ws.sent_text[0])
    assert reply["type"] == "registered"
    assert reply["devices"][0]["usb_serial"] == "usb-1"
    assert reply["devices"][0]["serial"] == "127.0.0.1:28100"
    assert "error" not in reply["devices"][0]
    assert session.devices["usb-1"].meta["model"] == "M"
    assert keeper.count == 1
    await session.shutdown_sender()


@pytest.mark.asyncio
async def test_on_control_devices_reply_failure_is_swallowed(monkeypatch):
    """devices 更新后的 registered 回执发送失败不中断，且仍通知 keeper。"""
    ws = _FakeWebSocket()
    ws.fail_text = True
    hub = th.TunnelHub()
    keeper = _KeeperRecorder()
    hub.set_keeper(keeper)
    session = th.AgentSession(hub, ws, "agent-a", 1)

    async def _no_devices(_agent_session, _raw_devices):
        return [], []

    monkeypatch.setattr(hub, "_apply_device_list", _no_devices)
    await hub._on_control(session, {"type": "devices", "devices": []})

    assert keeper.count == 1
    await _wait_until(lambda: session.closed)


@pytest.mark.asyncio
async def test_on_control_open_result_and_close_handle_connections():
    ws = _FakeWebSocket()
    session = _new_agent_session(ws=ws)
    writer1, writer2, writer3 = _FakeStreamWriter(), _FakeStreamWriter(), _FakeStreamWriter()
    conn1, conn2, conn3 = _make_conn(11, writer=writer1), _make_conn(12, writer=writer2), _make_conn(13, writer=writer3)
    session.conns.update({11: conn1, 12: conn2, 13: conn3})

    await HUB._on_control(session, {"type": "open_result", "conn_id": 11, "ok": False})
    assert conn1.closed and writer1.closed and 11 not in session.conns

    await HUB._on_control(session, {"type": "open_result", "conn_id": 12, "ok": True})
    assert conn2.closed is False and 12 in session.conns

    await HUB._on_control(session, {"type": "close", "conn_id": 13})
    assert conn3.closed and 13 not in session.conns

    await HUB._on_control(session, {"type": "close", "conn_id": 404})  # 未知 conn_id 不抛错
    assert ws.sent_text == []  # notify_agent=False，不向 Agent 回发


@pytest.mark.asyncio
async def test_on_control_unknown_type_is_ignored():
    session = _new_agent_session()
    await HUB._on_control(session, {"type": "mystery"})
    assert session.link_rtt_ms is None and session.conns == {}


@pytest.mark.asyncio
async def test_on_data_frame_ignores_short_frames():
    ws = _FakeWebSocket()
    session = _new_agent_session(ws=ws)
    await HUB._on_data_frame(session, b"\x00")
    assert ws.sent_text == [] and session.conns == {}


@pytest.mark.asyncio
async def test_on_data_frame_oversize_payload_closes_conn(monkeypatch):
    monkeypatch.setattr(th, "MAX_DATA_PAYLOAD", 4)
    ws = _FakeWebSocket()
    session = _new_agent_session(ws=ws)
    writer = _FakeStreamWriter()
    session.conns[5] = _make_conn(5, writer=writer)

    await HUB._on_data_frame(session, th.encode_data_frame(5, b"12345"))

    assert 5 not in session.conns and writer.closed
    assert json.loads(ws.sent_text[-1]) == {"type": "close", "conn_id": 5}


@pytest.mark.asyncio
async def test_on_data_frame_unknown_or_closed_conn_asks_agent_to_close():
    ws = _FakeWebSocket()
    session = _new_agent_session(ws=ws)
    await HUB._on_data_frame(session, th.encode_data_frame(9, b"x"))
    assert json.loads(ws.sent_text[-1]) == {"type": "close", "conn_id": 9}

    closed_conn = _make_conn(10)
    closed_conn.closed = True
    session.conns[10] = closed_conn
    await HUB._on_data_frame(session, th.encode_data_frame(10, b"x"))
    assert json.loads(ws.sent_text[-1]) == {"type": "close", "conn_id": 10}

    ws2 = _FakeWebSocket()
    ws2.fail_text = True
    session2 = _new_agent_session(ws=ws2)
    await HUB._on_data_frame(session2, th.encode_data_frame(1, b"x"))  # 回发失败被静默吞掉
    await _wait_until(lambda: ws2.closed)


@pytest.mark.asyncio
async def test_on_data_frame_queue_full_closes_conn():
    ws = _FakeWebSocket()
    session = _new_agent_session(ws=ws)
    writer = _FakeStreamWriter()
    conn = _make_conn(2, writer=writer)
    conn.write_queue = asyncio.Queue(maxsize=1)
    conn.write_queue.put_nowait(b"occupied")
    session.conns[2] = conn

    await HUB._on_data_frame(session, th.encode_data_frame(2, b"blocked"))

    assert conn.closed and 2 not in session.conns and writer.closed
    assert json.loads(ws.sent_text[-1]) == {"type": "close", "conn_id": 2}


@pytest.mark.asyncio
async def test_on_data_frame_enqueues_payload_for_drain():
    session = _new_agent_session()
    conn = _make_conn(4)
    session.conns[4] = conn
    await HUB._on_data_frame(session, th.encode_data_frame(4, b"hello"))
    assert conn.write_queue.get_nowait() == b"hello"
    assert session.inbound_rate.rate_bps() > 0


# ==================== 设备列表与监听器 ====================


@pytest.mark.asyncio
async def test_apply_device_list_ignores_entries_without_usb_serial(db_engine):
    session = _new_agent_session(agent_id=1)
    accepted, rejected = await HUB._apply_device_list(session, [None, {}, {"usb_serial": "   "}])
    assert accepted == [] and rejected == [] and session.devices == {}


@pytest.mark.asyncio
async def test_apply_device_list_creates_removes_and_updates(db_engine, monkeypatch):
    servers = _patch_fake_start_server(monkeypatch)
    session = _new_agent_session(agent_id=1)

    accepted, rejected = await HUB._apply_device_list(
        session, [{"usb_serial": "usb-1"}, {"usb_serial": "usb-2", "model": "M2"}]
    )
    assert rejected == [] and {e["usb_serial"] for e in accepted} == {"usb-1", "usb-2"}
    runtime2 = session.devices["usb-2"]
    assert runtime2.listener is not None and runtime2.ready
    assert runtime2.meta["model"] == "M2"

    writer = _FakeStreamWriter()
    conn = _make_conn(3, usb_serial="usb-2", writer=writer)
    session.conns[3] = conn

    accepted2, _ = await HUB._apply_device_list(session, [{"usb_serial": "usb-1", "model": "NewModel"}])

    assert "usb-2" not in session.devices
    assert servers[1].closed is True  # usb-2 的监听器已被关闭
    assert conn.closed is True and 3 not in session.conns and writer.closed
    assert session.devices["usb-1"].meta["model"] == "NewModel"
    assert accepted2[0]["usb_serial"] == "usb-1" and accepted2[0]["tunnel_port"] == accepted[0]["tunnel_port"]


@pytest.mark.asyncio
async def test_apply_device_list_reports_port_exhaustion(db_engine, monkeypatch):
    """端口耗尽时被拒绝的设备进入 rejected 列表，且不产生运行时。"""
    monkeypatch.setattr(th, "TUNNEL_PORT_RANGE_START", 28150)
    monkeypatch.setattr(th, "TUNNEL_PORT_RANGE_END", 28150)
    with Session(db_engine) as db:
        db.add(RemoteAgentDevice(agent_id=2, usb_serial="existing", tunnel_port=28150))
        db.commit()

    session = _new_agent_session(agent_id=2)
    accepted, rejected = await HUB._apply_device_list(session, [{"usb_serial": "usb-1"}])

    assert accepted == [] and session.devices == {}
    assert rejected[0]["usb_serial"] == "usb-1" and "耗尽" in rejected[0]["error"]


@pytest.mark.asyncio
async def test_apply_device_list_surfaces_listener_error_in_accepted_entry(db_engine, monkeypatch):
    _patch_fake_start_server(monkeypatch, error=OSError("port busy"))
    session = _new_agent_session(agent_id=1)

    accepted, rejected = await HUB._apply_device_list(session, [{"usb_serial": "usb-1"}])

    assert rejected == [] and "error" in accepted[0]
    assert accepted[0]["error"].startswith("隧道端口 28100 监听失败")
    assert session.devices["usb-1"].ready is False


@pytest.mark.asyncio
async def test_start_listener_binds_real_port_and_reports_ready():
    port = _free_tcp_port()
    session = _new_agent_session()
    runtime = _make_runtime("usb-1", port)

    await HUB._start_listener(session, runtime)

    assert runtime.listener is not None and runtime.ready and runtime.error is None
    runtime.listener.close()
    await runtime.listener.wait_closed()


@pytest.mark.asyncio
async def test_start_listener_client_handler_delegates_to_tunnel_client(monkeypatch):
    """监听器收到客户端连接时把处理转给 _handle_tunnel_client。"""
    servers = _patch_fake_start_server(monkeypatch)
    ws = _FakeWebSocket()
    session = _new_agent_session(ws=ws)
    runtime = _make_runtime("usb-1", 28100)
    await HUB._start_listener(session, runtime)

    reader = asyncio.StreamReader()
    writer = _FakeStreamWriter()
    task = asyncio.create_task(servers[0].handler(reader, writer))
    await _wait_until(lambda: any(json.loads(t).get("type") == "open" for t in ws.sent_text))
    reader.feed_eof()
    await asyncio.wait_for(task, timeout=2)

    assert writer.closed is True and session.conns == {}


@pytest.mark.asyncio
async def test_start_listener_oserror_records_error():
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.bind(("127.0.0.1", 0))
    sock.listen(1)
    port = int(sock.getsockname()[1])
    try:
        session = _new_agent_session()
        runtime = _make_runtime("usb-1", port)
        await HUB._start_listener(session, runtime)
        assert runtime.listener is None and runtime.ready is False
        assert "监听失败" in runtime.error
    finally:
        sock.close()


@pytest.mark.asyncio
async def test_remove_device_runtime_missing_serial_is_noop():
    session = _new_agent_session()
    await HUB._remove_device_runtime(session, "nope")
    assert session.devices == {}


@pytest.mark.asyncio
async def test_remove_device_runtime_without_listener_skips_close_block():
    """监听器为空（启动失败）的设备直接删除，不进入关闭分支。"""
    session = _new_agent_session()
    session.devices["usb-1"] = _make_runtime("usb-1", 28100)

    await HUB._remove_device_runtime(session, "usb-1")

    assert session.devices == {}


@pytest.mark.asyncio
async def test_remove_device_runtime_closes_listener_and_only_matching_conns():
    ws = _FakeWebSocket()
    session = _new_agent_session(ws=ws)
    server = _FakeServer()
    server.wait_closed_error = RuntimeError("wait failed")
    session.devices["usb-1"] = _make_runtime("usb-1", 28100, listener=server)
    writer_a = _FakeStreamWriter()
    conn_a = _make_conn(1, usb_serial="usb-1", writer=writer_a)
    conn_b = _make_conn(2, usb_serial="usb-2", writer=_FakeStreamWriter())
    session.conns.update({1: conn_a, 2: conn_b})

    await HUB._remove_device_runtime(session, "usb-1")

    assert "usb-1" not in session.devices
    assert server.closed is True and conn_a.closed is True and writer_a.closed is True
    assert conn_b.closed is False and 2 in session.conns
    assert any(json.loads(t) == {"type": "close", "conn_id": 1} for t in ws.sent_text)


# ==================== 隧道连接与连接关闭 ====================


@pytest.mark.asyncio
async def test_handle_tunnel_client_rejects_closed_session():
    ws = _FakeWebSocket()
    session = _new_agent_session(ws=ws)
    session.closed = True
    writer = _FakeStreamWriter()

    await HUB._handle_tunnel_client(session, _make_runtime("usb-1", 28100), asyncio.StreamReader(), writer)

    assert writer.closed is True
    assert ws.sent_text == [] and session.conns == {}


@pytest.mark.asyncio
async def test_handle_tunnel_client_pumps_data_and_notifies_close():
    ws = _FakeWebSocket()
    session = _new_agent_session(ws=ws)
    sock = _FakeSock()
    writer = _FakeStreamWriter(sock=sock)
    reader = asyncio.StreamReader()

    task = asyncio.create_task(HUB._handle_tunnel_client(session, _make_runtime("usb-1", 28100), reader, writer))
    await _wait_until(lambda: any(json.loads(t).get("type") == "open" for t in ws.sent_text))
    assert sock.calls == [(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)]

    reader.feed_data(b"adb-hello-more")
    await _wait_until(lambda: ws.sent_bytes)  # 等 sender 发完数据帧，读循环才能安全收尾
    reader.feed_eof()
    await asyncio.wait_for(task, timeout=2)

    frames = [th.decode_data_frame(f) for f in ws.sent_bytes]
    assert b"".join(payload for _, payload in frames) == b"adb-hello-more"
    assert all(conn_id == 1 for conn_id, _ in frames)
    assert any(json.loads(t) == {"type": "close", "conn_id": 1} for t in ws.sent_text)
    assert writer.closed is True and session.conns == {}


@pytest.mark.asyncio
async def test_handle_tunnel_client_open_failure_closes_conn():
    ws = _FakeWebSocket()
    ws.fail_text = True
    session = _new_agent_session(ws=ws)
    writer = _FakeStreamWriter()

    await HUB._handle_tunnel_client(session, _make_runtime("usb-1", 28100), asyncio.StreamReader(), writer)

    assert writer.closed is True and session.conns == {}
    await _wait_until(lambda: ws.closed)


@pytest.mark.asyncio
async def test_handle_tunnel_client_read_error_still_closes_and_notifies(monkeypatch):
    ws = _FakeWebSocket()
    session = _new_agent_session(ws=ws)
    writer = _FakeStreamWriter()
    reader = asyncio.StreamReader()

    async def _boom(conn_id, data):
        raise ConnectionError("send failed")

    monkeypatch.setattr(session, "send_data", _boom)

    task = asyncio.create_task(HUB._handle_tunnel_client(session, _make_runtime("usb-1", 28100), reader, writer))
    await _wait_until(lambda: any(json.loads(t).get("type") == "open" for t in ws.sent_text))
    reader.feed_data(b"data")
    reader.feed_eof()
    await asyncio.wait_for(task, timeout=2)

    assert writer.closed is True and session.conns == {}
    assert any(json.loads(t) == {"type": "close", "conn_id": 1} for t in ws.sent_text)


@pytest.mark.asyncio
async def test_handle_tunnel_client_swallows_get_extra_info_error():
    ws = _FakeWebSocket()
    session = _new_agent_session(ws=ws)
    writer = _FakeStreamWriter(extra_error=True)
    reader = asyncio.StreamReader()

    task = asyncio.create_task(HUB._handle_tunnel_client(session, _make_runtime("usb-1", 28100), reader, writer))
    await _wait_until(lambda: any(json.loads(t).get("type") == "open" for t in ws.sent_text))
    reader.feed_eof()
    await asyncio.wait_for(task, timeout=2)
    assert writer.closed is True


@pytest.mark.asyncio
async def test_handle_tunnel_client_swallows_setsockopt_error():
    ws = _FakeWebSocket()
    session = _new_agent_session(ws=ws)
    writer = _FakeStreamWriter(sock=_FakeSock(fail=True))
    reader = asyncio.StreamReader()

    task = asyncio.create_task(HUB._handle_tunnel_client(session, _make_runtime("usb-1", 28100), reader, writer))
    await _wait_until(lambda: any(json.loads(t).get("type") == "open" for t in ws.sent_text))
    reader.feed_eof()
    await asyncio.wait_for(task, timeout=2)
    assert writer.closed is True


@pytest.mark.asyncio
async def test_handle_tunnel_client_skips_final_close_when_conn_already_closed(monkeypatch):
    """open 期间连接被外部关闭：读循环直接退出，finally 不重复关闭连接。"""
    ws = _FakeWebSocket()
    session = _new_agent_session(ws=ws)
    writer = _FakeStreamWriter()
    reader = asyncio.StreamReader()
    gate = asyncio.Event()
    original_send_control = session.send_control

    async def _gated_send_control(payload):
        await gate.wait()
        await original_send_control(payload)

    monkeypatch.setattr(session, "send_control", _gated_send_control)

    task = asyncio.create_task(HUB._handle_tunnel_client(session, _make_runtime("usb-1", 28100), reader, writer))
    await _wait_until(lambda: 1 in session.conns)
    conn = session.conns[1]
    drain = conn.writer_task

    await HUB._close_conn(session, 1, notify_agent=False, cancel_pump=False)
    assert conn.closed is True and 1 not in session.conns
    gate.set()
    await asyncio.wait_for(task, timeout=2)

    assert writer.closed is True
    with pytest.raises(asyncio.CancelledError):
        await drain
    await session.shutdown_sender()


@pytest.mark.asyncio
async def test_drain_tunnel_connection_writes_payloads():
    session = _new_agent_session()
    writer = _FakeStreamWriter()
    conn = _make_conn(5, writer=writer)
    session.conns[5] = conn
    conn.write_queue.put_nowait(b"to-adb")

    task = asyncio.create_task(HUB._drain_tunnel_connection(session, conn))
    await _wait_until(lambda: writer.writes == [b"to-adb"])
    assert writer.drain_calls == 1

    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task


@pytest.mark.asyncio
async def test_drain_tunnel_connection_error_closes_conn():
    ws = _FakeWebSocket()
    session = _new_agent_session(ws=ws)
    writer = _FakeStreamWriter()
    writer.drain_error = RuntimeError("drain broke")
    conn = _make_conn(5, writer=writer)
    session.conns[5] = conn
    conn.write_queue.put_nowait(b"x")

    await HUB._drain_tunnel_connection(session, conn)

    assert conn.closed and 5 not in session.conns and writer.closed
    assert any(json.loads(t) == {"type": "close", "conn_id": 5} for t in ws.sent_text)


@pytest.mark.asyncio
async def test_drain_tunnel_connection_closed_paths():
    """drain 在连接已关闭时的两条早退路径。"""
    session = _new_agent_session()

    # 进入时已关闭 → 循环体不执行
    writer1 = _FakeStreamWriter()
    conn1 = _make_conn(5, writer=writer1)
    conn1.closed = True
    await asyncio.wait_for(HUB._drain_tunnel_connection(session, conn1), timeout=2)
    assert writer1.writes == []

    # 循环中写出失败但连接已关闭 → 不再回发 close，异常被吞掉
    writer2 = _FakeStreamWriter()
    writer2.drain_error = RuntimeError("drain broke")
    conn2 = _make_conn(6, writer=writer2)
    session.conns[6] = conn2
    task = asyncio.create_task(HUB._drain_tunnel_connection(session, conn2))
    await asyncio.sleep(0.01)  # 让 drain 停在 write_queue.get()
    conn2.closed = True
    conn2.write_queue.put_nowait(b"x")
    await asyncio.wait_for(task, timeout=2)
    assert writer2.writes == [b"x"] and 6 in session.conns


@pytest.mark.asyncio
async def test_close_conn_ignores_unknown_and_already_closed_connections():
    session = _new_agent_session()
    await HUB._close_conn(session, 42, notify_agent=False)  # 未知 conn → 直接返回

    writer = _FakeStreamWriter()
    conn = _make_conn(43, writer=writer)
    conn.closed = True
    session.conns[43] = conn
    await HUB._close_conn(session, 43, notify_agent=False)
    assert writer.closed is False and 43 not in session.conns  # 已关闭连接不再重复处理


@pytest.mark.asyncio
async def test_close_conn_cancels_pump_and_writer_tasks():
    ws = _FakeWebSocket()
    session = _new_agent_session(ws=ws)
    writer = _FakeStreamWriter()
    conn = _make_conn(6, writer=writer)
    pump = asyncio.create_task(asyncio.sleep(30))
    drain = asyncio.create_task(asyncio.sleep(30))
    conn.pump_task = pump
    conn.writer_task = drain
    session.conns[6] = conn

    await HUB._close_conn(session, 6, notify_agent=True)

    assert conn.closed and writer.closed and 6 not in session.conns
    assert json.loads(ws.sent_text[-1]) == {"type": "close", "conn_id": 6}
    with pytest.raises(asyncio.CancelledError):
        await pump
    with pytest.raises(asyncio.CancelledError):
        await drain
    assert pump.cancelled() and drain.cancelled()


@pytest.mark.asyncio
async def test_close_conn_skips_current_task_and_closed_session_notify():
    ws = _FakeWebSocket()
    session = _new_agent_session(ws=ws)
    writer = _FakeStreamWriter()
    writer.close_error = RuntimeError("close failed")
    conn = _make_conn(8, writer=writer)
    current = asyncio.current_task()
    conn.pump_task = current
    conn.writer_task = current
    session.conns[8] = conn
    session.closed = True  # closed 会话不再回发 close 控制消息

    await HUB._close_conn(session, 8, notify_agent=True)

    assert conn.closed and 8 not in session.conns
    assert current.cancelling() == 0
    assert ws.sent_text == []


@pytest.mark.asyncio
async def test_close_conn_swallows_notify_failure():
    ws = _FakeWebSocket()
    ws.fail_text = True
    session = _new_agent_session(ws=ws)
    writer = _FakeStreamWriter()
    conn = _make_conn(44, writer=writer)
    session.conns[44] = conn

    await HUB._close_conn(session, 44, notify_agent=True)

    assert conn.closed and writer.closed
    await _wait_until(lambda: ws.closed)


# ==================== 会话生命周期 ====================


@pytest.mark.asyncio
async def test_teardown_session_full_cleanup(db_engine):
    agent_id = HUB._persist_agent_online("agent-a", {}, "admin")
    port_map, _ = HUB._persist_device_mappings(agent_id, {"usb-1": {"model": "M"}})
    serial = th.tunnel_serial(port_map["usb-1"])

    ws = _FakeWebSocket()
    session = _new_agent_session(name="agent-a", agent_id=agent_id, ws=ws)
    session.devices["usb-1"] = _make_runtime("usb-1", port_map["usb-1"], listener=_FakeServer())
    writer = _FakeStreamWriter()
    session.conns[2] = _make_conn(2, usb_serial="usb-1", writer=writer)
    session.conns[3] = _make_conn(3, usb_serial="usb-9", writer=_FakeStreamWriter())

    loop = asyncio.get_running_loop()
    pending = loop.create_future()
    done = loop.create_future()
    done.set_result("ok")
    session._probe_futures[1] = pending
    session._probe_futures[2] = done

    keeper = _KeeperRecorder()
    HUB.set_keeper(keeper)
    HUB._sessions["agent-a"] = session

    await HUB._teardown_session(session, reason="test")

    assert session.closed is True and "agent-a" not in HUB._sessions
    assert session.devices == {} and session.conns == {} and writer.closed
    with pytest.raises(ConnectionError):
        await pending
    assert done.result() == "ok"
    assert ws.closed is True and keeper.count == 1
    with Session(db_engine) as db:
        assert db.get(RemoteAgent, agent_id).status == "OFFLINE"
        dev = db.scalars(select(Device).where(Device.serial == serial)).one()
        assert dev.status == DeviceStatus.offline

    await HUB._teardown_session(session, reason="again")  # 幂等：已关闭直接返回
    assert keeper.count == 1


@pytest.mark.asyncio
async def test_teardown_session_keeps_replacement_session(db_engine):
    replacement = _new_agent_session(name="agent-x", agent_id=55)
    session = _new_agent_session(name="agent-x", agent_id=56)
    HUB._sessions["agent-x"] = replacement

    await HUB._teardown_session(session, reason="stale")

    assert session.closed is True
    assert HUB._sessions["agent-x"] is replacement  # 名字已属于新会话，不得误删


@pytest.mark.asyncio
async def test_shutdown_tears_down_all_sessions(db_engine):
    ws1, ws2 = _FakeWebSocket(), _FakeWebSocket()
    ws2.fail_close = True  # websocket.close 抛错被吞掉
    s1 = _new_agent_session(name="agent-a", agent_id=101, ws=ws1)
    s2 = _new_agent_session(name="agent-b", agent_id=102, ws=ws2)
    HUB._sessions.update({"agent-a": s1, "agent-b": s2})

    await HUB.shutdown()

    assert HUB._sessions == {}
    assert s1.closed and s2.closed and ws1.closed


@pytest.mark.asyncio
async def test_handle_session_full_lifecycle_with_device_and_controls(db_engine, monkeypatch):
    _patch_fake_start_server(monkeypatch)
    ws = _FakeWebSocket()
    keeper = _KeeperRecorder()
    HUB.set_keeper(keeper)
    ws.push(
        _register_message(devices=[{"usb_serial": "usb-1", "model": "Pixel 8", "brand": "Google", "os_version": "14"}])
    )

    task = asyncio.create_task(HUB.handle_session(ws, "admin"))
    await _wait_until(lambda: len(ws.sent_text) >= 1)

    registered = json.loads(ws.sent_text[0])
    assert registered["type"] == "registered"
    assert registered["protocol"] == th.AGENT_PROTOCOL_VERSION
    assert registered["devices"][0]["serial"] == "127.0.0.1:28100"
    assert registered["rejected"] == []
    assert HUB.is_agent_online("agent-a") is True
    with Session(db_engine) as db:
        assert db.scalars(select(RemoteAgent)).first().status == "ONLINE"
        mapping = db.scalars(select(RemoteAgentDevice)).one()
        assert mapping.usb_serial == "usb-1" and mapping.tunnel_port == 28100

    ws.push({"type": "websocket.receive", "text": json.dumps({"type": "ping", "rtt_ms": 8})})
    await _wait_until(lambda: any(json.loads(t).get("type") == "pong" for t in ws.sent_text))
    assert HUB._sessions["agent-a"].link_rtt_ms == 8.0

    ws.push({"type": "websocket.receive", "text": json.dumps({"type": "devices", "devices": []})})
    await _wait_until(lambda: len([t for t in ws.sent_text if json.loads(t)["type"] == "registered"]) == 2)
    assert HUB._sessions["agent-a"].devices == {}

    ws.push({"type": "websocket.disconnect"})
    await asyncio.wait_for(task, timeout=2)

    assert HUB.is_agent_online("agent-a") is False and HUB._sessions == {}
    assert ws.closed is True and keeper.count >= 3
    with Session(db_engine) as db:
        assert db.scalars(select(RemoteAgent)).first().status == "OFFLINE"


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("message", "fragment"),
    [
        ({"type": "websocket.receive", "text": "not-json"}, "不是合法 JSON"),
        ({"type": "websocket.receive", "text": "{}"}, "首条消息必须是 register"),
        ({"type": "websocket.receive", "bytes": b"\x00\x01"}, "首条消息必须是 JSON register"),
        (_register_message(name="   "), "缺失或过长"),
        (_register_message(name="x" * 65), "缺失或过长"),
        (_register_message(protocol=9), "协议版本不匹配"),
    ],
)
async def test_handle_session_rejects_invalid_registers(message, fragment):
    ws = _FakeWebSocket()
    ws.push(message)
    await asyncio.wait_for(HUB.handle_session(ws, "admin"), timeout=2)

    error = json.loads(ws.sent_text[-1])
    assert error["type"] == "error" and fragment in error["message"]
    assert ws.close_codes == [4400]
    assert HUB._sessions == {}


@pytest.mark.asyncio
async def test_handle_session_ignores_disconnect_as_first_message():
    ws = _FakeWebSocket()
    ws.push({"type": "websocket.disconnect"})
    await asyncio.wait_for(HUB.handle_session(ws, "admin"), timeout=2)
    assert ws.sent_text == [] and HUB._sessions == {}


@pytest.mark.asyncio
async def test_handle_session_gives_up_on_register_timeout(monkeypatch):
    monkeypatch.setattr(th, "REGISTER_TIMEOUT_SECONDS", 0.05)
    ws = _FakeWebSocket()
    await asyncio.wait_for(HUB.handle_session(ws, "admin"), timeout=2)
    assert ws.sent_text == [] and HUB._sessions == {}


@pytest.mark.asyncio
async def test_wait_register_returns_none_on_disconnect_exception():
    ws = _FakeWebSocket()
    ws.raise_after_inbox_empty = WebSocketDisconnect(1006)
    assert await HUB._wait_register(ws) is None


@pytest.mark.asyncio
async def test_handle_session_replaces_stale_session(db_engine, monkeypatch):
    _patch_fake_start_server(monkeypatch)
    stale_ws = _FakeWebSocket()
    stale = _new_agent_session(name="agent-a", agent_id=999, ws=stale_ws)
    HUB._sessions["agent-a"] = stale

    ws = _FakeWebSocket()
    ws.push(_register_message(name="agent-a"))
    task = asyncio.create_task(HUB.handle_session(ws, "admin"))
    await _wait_until(lambda: stale.closed and HUB._sessions.get("agent-a") is not stale)
    assert stale_ws.closed is True

    ws.push({"type": "websocket.disconnect"})
    await asyncio.wait_for(task, timeout=2)
    assert HUB._sessions == {}


@pytest.mark.asyncio
async def test_handle_session_teardown_on_internal_error(db_engine, monkeypatch):
    _patch_fake_start_server(monkeypatch)
    ws = _FakeWebSocket()
    ws.push(_register_message())

    async def _boom(session):
        raise RuntimeError("receive exploded")

    monkeypatch.setattr(HUB, "_receive_loop", _boom)

    await asyncio.wait_for(HUB.handle_session(ws, "admin"), timeout=2)

    assert HUB._sessions == {} and ws.closed is True
    with Session(db_engine) as db:
        assert db.scalars(select(RemoteAgent)).first().status == "OFFLINE"


@pytest.mark.asyncio
async def test_handle_session_disconnect_exception_is_absorbed(db_engine, monkeypatch):
    _patch_fake_start_server(monkeypatch)
    ws = _FakeWebSocket()
    ws.push(_register_message())
    ws.raise_after_inbox_empty = WebSocketDisconnect(1006)

    await asyncio.wait_for(HUB.handle_session(ws, "admin"), timeout=2)

    assert HUB._sessions == {} and ws.closed is True


@pytest.mark.asyncio
async def test_reject_swallows_send_and_close_failures():
    ws = _FakeWebSocket()
    ws.fail_text = True
    ws.fail_close = True
    await HUB._reject(ws, "nope")  # 不抛异常
    assert ws.close_codes == [4400]


@pytest.mark.asyncio
async def test_receive_loop_returns_immediately_when_session_closed():
    """会话已关闭时接收循环直接退出（while 假分支）。"""
    session = _new_agent_session()
    session.closed = True
    await asyncio.wait_for(HUB._receive_loop(session), timeout=2)


@pytest.mark.asyncio
async def test_receive_loop_idle_timeout_returns(monkeypatch):
    monkeypatch.setattr(th, "SESSION_IDLE_TIMEOUT_SECONDS", 0.05)
    session = _new_agent_session()
    await asyncio.wait_for(HUB._receive_loop(session), timeout=2)
    assert session.closed is False


@pytest.mark.asyncio
async def test_receive_loop_skips_empty_and_invalid_messages():
    ws = _FakeWebSocket()
    session = _new_agent_session(ws=ws)
    ws.push({"type": "websocket.receive"})  # text/bytes 均为空 → 跳过
    ws.push({"type": "websocket.receive", "text": "{bad"})  # 非法 JSON → 跳过
    ws.push({"type": "websocket.receive", "text": json.dumps({"type": "ping"})})
    ws.push({"type": "websocket.disconnect"})

    await asyncio.wait_for(HUB._receive_loop(session), timeout=2)

    assert any(json.loads(t) == {"type": "pong"} for t in ws.sent_text)
    await session.shutdown_sender()


@pytest.mark.asyncio
async def test_receive_loop_routes_binary_frames():
    ws = _FakeWebSocket()
    session = _new_agent_session(ws=ws)
    conn = _make_conn(3)
    session.conns[3] = conn
    ws.push({"type": "websocket.receive", "bytes": th.encode_data_frame(3, b"payload")})
    ws.push({"type": "websocket.disconnect"})

    await asyncio.wait_for(HUB._receive_loop(session), timeout=2)

    assert conn.write_queue.get_nowait() == b"payload"
