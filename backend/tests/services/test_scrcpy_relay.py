"""Unit tests for the cross-worker Redis Scrcpy relay service and Worker relay agent."""

from __future__ import annotations

import asyncio
from collections import deque
import json
import threading
import time
from types import SimpleNamespace

import pytest

from app.services import scrcpy_relay
from app.services.scrcpy_relay import (
    FRAME_ERROR,
    FRAME_HEARTBEAT,
    FRAME_METADATA,
    FRAME_VIDEO,
    RemoteScrcpyStream,
    ScrcpyRelayError,
    ScrcpyWorkerRelayAgent,
    decode_relay_frame,
    encode_relay_frame,
    open_remote_scrcpy_stream,
    request_remote_scrcpy_reconnect,
    stream_output_channel,
    worker_ctrl_channel,
)


class _InMemoryBroker:
    """Thread-safe in-memory Pub/Sub broker supporting both sync and async clients."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._subs: dict[str, list[tuple[asyncio.AbstractEventLoop | None, object]]] = {}
        self.published: list[tuple[str, bytes]] = []

    def subscribe_sync(self, channel: str, out_queue: deque[bytes]) -> None:
        with self._lock:
            self._subs.setdefault(channel, []).append((None, out_queue))

    def subscribe_async(self, channel: str, loop: asyncio.AbstractEventLoop, out_queue: asyncio.Queue) -> None:
        with self._lock:
            self._subs.setdefault(channel, []).append((loop, out_queue))

    def unsubscribe(self, channel: str, target: object) -> None:
        with self._lock:
            subs = self._subs.get(channel)
            if not subs:
                return
            self._subs[channel] = [(lp, q) for lp, q in subs if q is not target]

    def publish(self, channel: str, data: bytes) -> int:
        with self._lock:
            self.published.append((channel, data))
            targets = list(self._subs.get(channel, []))
        for loop, target in targets:
            if loop is None:
                assert isinstance(target, deque)
                target.append(data)
            else:
                assert isinstance(target, asyncio.Queue)
                loop.call_soon_threadsafe(target.put_nowait, data)
        return len(targets)


class _SyncPubSub:
    def __init__(self, broker: _InMemoryBroker) -> None:
        self._broker = broker
        self._channels: list[str] = []
        self._queue: deque[bytes] = deque()

    def subscribe(self, channel: str) -> None:
        self._channels.append(channel)
        self._broker.subscribe_sync(channel, self._queue)

    def get_message(self, ignore_subscribe_messages: bool = True, timeout: float = 0.0):
        del ignore_subscribe_messages, timeout
        if not self._queue:
            return None
        return {"type": "message", "data": self._queue.popleft()}

    def close(self) -> None:
        for channel in self._channels:
            self._broker.unsubscribe(channel, self._queue)
        self._channels.clear()


class _FakeSyncRedis:
    def __init__(self, broker: _InMemoryBroker) -> None:
        self._broker = broker
        self.closed = False

    def pubsub(self) -> _SyncPubSub:
        return _SyncPubSub(self._broker)

    def publish(self, channel: str, data: bytes) -> int:
        return self._broker.publish(channel, data)

    def close(self) -> None:
        self.closed = True


class _AsyncPubSub:
    def __init__(self, broker: _InMemoryBroker) -> None:
        self._broker = broker
        self._channels: list[str] = []
        self._queue: asyncio.Queue[bytes] = asyncio.Queue()

    async def subscribe(self, channel: str) -> None:
        loop = asyncio.get_running_loop()
        self._channels.append(channel)
        self._broker.subscribe_async(channel, loop, self._queue)

    async def unsubscribe(self, channel: str) -> None:
        self._broker.unsubscribe(channel, self._queue)
        if channel in self._channels:
            self._channels.remove(channel)

    async def get_message(self, ignore_subscribe_messages: bool = True, timeout: float = 0.5):
        del ignore_subscribe_messages
        try:
            data = await asyncio.wait_for(self._queue.get(), timeout=timeout)
        except TimeoutError:
            return None
        return {"type": "message", "data": data}

    async def aclose(self) -> None:
        for channel in list(self._channels):
            self._broker.unsubscribe(channel, self._queue)
        self._channels.clear()


class _FakeAsyncRedis:
    def __init__(self, broker: _InMemoryBroker) -> None:
        self._broker = broker
        self.closed = False

    def pubsub(self) -> _AsyncPubSub:
        return _AsyncPubSub(self._broker)

    async def publish(self, channel: str, data: bytes) -> int:
        return self._broker.publish(channel, data)

    async def aclose(self) -> None:
        self.closed = True


class _FakeClientStream:
    def __init__(self, serial: str, chunks: list[bytes | None]) -> None:
        self.dev_info = SimpleNamespace(
            serial=serial,
            screen_width=1080,
            screen_height=1920,
            device_name="OPPO R11",
            error=None,
        )
        self._chunks = deque(chunks)
        self.closed = False

    def get_chunk(self, timeout: float = 0.5):
        del timeout
        if self.closed:
            return None
        if self._chunks:
            return self._chunks.popleft()
        time.sleep(0.02)
        return b""

    def close(self) -> None:
        self.closed = True


class _FakeScrcpyManager:
    def __init__(self, chunks: list[bytes | None] | None = None) -> None:
        self.chunks = chunks if chunks is not None else [b"\x00\x00\x00\x01sps", b"\x00\x00\x00\x01idr"]
        self.streams: list[_FakeClientStream] = []
        self.touch_calls: list[tuple] = []
        self.key_calls: list[tuple] = []
        self.text_calls: list[tuple] = []
        self.cleanup_calls: list[str] = []
        self.cleanup_all_called = 0
        self.start_error: Exception | None = None

    def create_client_stream(self, serial: str):
        if self.start_error is not None:
            raise self.start_error
        stream = _FakeClientStream(serial, list(self.chunks))
        self.streams.append(stream)
        return stream

    def ensure_device_stream(self, serial: str):
        if self.start_error is not None:
            raise self.start_error
        return SimpleNamespace(serial=serial, screen_width=1080, screen_height=1920, device_name="OPPO R11")

    def send_touch_event(self, serial: str, action: int, x: int, y: int, width=None, height=None) -> None:
        self.touch_calls.append((serial, action, x, y, width, height))

    def send_key_event(self, serial: str, keycode: int) -> None:
        self.key_calls.append((serial, keycode))

    def send_text_event(self, serial: str, text: str) -> None:
        self.text_calls.append((serial, text))

    def _cleanup_device(self, serial: str) -> None:
        self.cleanup_calls.append(serial)

    def cleanup_all(self) -> None:
        self.cleanup_all_called += 1


def test_frame_encode_and_decode_roundtrip():
    raw = encode_relay_frame(FRAME_VIDEO, b"\x00\x00\x00\x01\x65frame")
    kind, payload = decode_relay_frame(raw)
    assert kind == FRAME_VIDEO
    assert payload == b"\x00\x00\x00\x01\x65frame"

    with pytest.raises(ValueError):
        encode_relay_frame(99, b"")
    with pytest.raises(ValueError):
        decode_relay_frame(b"")
    with pytest.raises(ValueError):
        decode_relay_frame(b"\x7fhello")


def test_worker_relay_agent_streams_video_handles_controls_and_stops():
    broker = _InMemoryBroker()
    manager = _FakeScrcpyManager(chunks=[b"sps-chunk", b"idr-chunk"])
    agent = ScrcpyWorkerRelayAgent(
        worker_id="worker-win",
        instance_generation=7,
        redis_client=_FakeSyncRedis(broker),
        manager=manager,
        idle_ttl_seconds=10.0,
    )
    out_queue: deque[bytes] = deque()
    channel = stream_output_channel("stream-1")
    broker.subscribe_sync(channel, out_queue)

    agent.process_control_message(
        {
            "type": "start",
            "stream_id": "stream-1",
            "serial": "SER-1",
            "expected_generation": 7,
        }
    )

    deadline = time.monotonic() + 2.0
    while len(out_queue) < 3 and time.monotonic() < deadline:
        time.sleep(0.01)

    decoded = [decode_relay_frame(item) for item in list(out_queue)]
    assert decoded[0][0] == FRAME_METADATA
    meta = json.loads(decoded[0][1].decode("utf-8"))
    assert meta == {"serial": "SER-1", "width": 1080, "height": 1920, "device_name": "OPPO R11"}
    assert decoded[1] == (FRAME_VIDEO, b"sps-chunk")
    assert decoded[2] == (FRAME_VIDEO, b"idr-chunk")

    agent.process_control_message(
        {
            "type": "touch",
            "serial": "SER-1",
            "action": 0,
            "x": 120,
            "y": 340,
            "w": 1080,
            "h": 1920,
            "expected_generation": 7,
        }
    )
    agent.process_control_message({"type": "key", "serial": "SER-1", "keycode": 4, "expected_generation": 7})
    agent.process_control_message({"type": "text", "serial": "SER-1", "text": "hello", "expected_generation": 7})
    # Mismatched generation must be ignored for control commands
    agent.process_control_message({"type": "key", "serial": "SER-1", "keycode": 26, "expected_generation": 6})

    assert manager.touch_calls == [("SER-1", 0, 120, 340, 1080, 1920)]
    assert manager.key_calls == [("SER-1", 4)]
    assert manager.text_calls == [("SER-1", "hello")]

    agent.process_control_message(
        {"type": "stop", "stream_id": "stream-1", "serial": "SER-1", "expected_generation": 7}
    )
    agent.stop(timeout=2.0)

    assert len(manager.streams) == 1
    assert manager.streams[0].closed is True
    assert manager.cleanup_all_called == 1


def test_worker_relay_agent_rejects_mismatched_generation_and_expires_idle_sessions():
    broker = _InMemoryBroker()
    manager = _FakeScrcpyManager(chunks=[b"first"])
    agent = ScrcpyWorkerRelayAgent(
        worker_id="worker-win",
        instance_generation=9,
        redis_client=_FakeSyncRedis(broker),
        manager=manager,
        idle_ttl_seconds=0.05,
    )
    err_queue: deque[bytes] = deque()
    broker.subscribe_sync(stream_output_channel("stale-gen"), err_queue)
    agent.process_control_message(
        {"type": "start", "stream_id": "stale-gen", "serial": "SER-1", "expected_generation": 8}
    )
    assert len(err_queue) == 1
    kind, payload = decode_relay_frame(err_queue.popleft())
    assert kind == FRAME_ERROR
    assert json.loads(payload.decode("utf-8"))["code"] == "worker_generation_mismatch"
    assert manager.streams == []

    # Active stream expires automatically without pings
    agent.process_control_message({"type": "start", "stream_id": "idle-1", "serial": "SER-1", "expected_generation": 9})
    time.sleep(0.08)
    agent._reap_expired_sessions()
    deadline = time.monotonic() + 2.0
    while len(manager.streams) == 0 or (not manager.streams[0].closed and time.monotonic() < deadline):
        time.sleep(0.01)
    assert manager.streams[0].closed is True
    agent.stop(timeout=2.0)


def test_end_to_end_async_remote_stream_and_reconnect():
    async def scenario():
        broker = _InMemoryBroker()
        manager = _FakeScrcpyManager(chunks=[b"annexb-sps", b"annexb-idr"])
        agent = ScrcpyWorkerRelayAgent(
            worker_id="win-node",
            instance_generation=12,
            redis_client=_FakeSyncRedis(broker),
            manager=manager,
            heartbeat_interval_seconds=0.05,
        )
        agent.start()
        try:
            # Give the background control thread a moment to subscribe cleanly
            await asyncio.sleep(0.05)

            ack = await request_remote_scrcpy_reconnect(
                "win-node",
                "DEV-R11",
                expected_generation=12,
                force=True,
                timeout=3.0,
                redis_factory=lambda: _FakeAsyncRedis(broker),
            )
            assert ack["ok"] is True
            assert manager.cleanup_calls == ["DEV-R11"]

            session = await open_remote_scrcpy_stream(
                "win-node",
                "DEV-R11",
                expected_generation=12,
                ready_timeout=3.0,
                redis_factory=lambda: _FakeAsyncRedis(broker),
            )
            assert session.metadata["device_name"] == "OPPO R11"
            chunk1 = await session.recv_chunk(timeout=1.5)
            chunk2 = await session.recv_chunk(timeout=1.5)
            assert chunk1 == b"annexb-sps"
            assert chunk2 == b"annexb-idr"

            await session.send_touch(0, 10, 20, 1080, 1920)
            await session.send_key(3)
            await session.send_text("abc")
            await asyncio.sleep(0.1)

            assert ("DEV-R11", 0, 10, 20, 1080, 1920) in manager.touch_calls
            assert ("DEV-R11", 3) in manager.key_calls
            assert ("DEV-R11", "abc") in manager.text_calls

            await session.close()
        finally:
            agent.stop(timeout=2.0)

    asyncio.run(scenario())


def test_remote_scrcpy_stream_maps_errors_and_drops_overflow_frames():
    async def scenario():
        broker = _InMemoryBroker()
        stream = RemoteScrcpyStream(
            worker_id="win-err",
            serial="SER-ERR",
            expected_generation=3,
            redis_factory=lambda: _FakeAsyncRedis(broker),
        )

        # Inject an error frame immediately after start publishes to worker ctrl channel
        async def _fail_worker():
            ctrl = worker_ctrl_channel("win-err")
            while not any(ch == ctrl for ch, _ in broker.published):
                await asyncio.sleep(0.005)
            broker.publish(
                stream.stream_channel,
                encode_relay_frame(
                    FRAME_ERROR,
                    json.dumps({"code": "scrcpy_start_failed", "message": "adb rejected"}).encode("utf-8"),
                ),
            )

        injector = asyncio.create_task(_fail_worker())
        with pytest.raises(ScrcpyRelayError) as exc_info:
            await stream.start(ready_timeout=2.0)
        await injector
        assert exc_info.value.code == "scrcpy_start_failed"
        assert "adb rejected" in exc_info.value.message

        # Verify bounded queue drop on burst frames
        stream2 = RemoteScrcpyStream(
            worker_id="win-burst",
            serial="SER-BURST",
            redis_factory=lambda: _FakeAsyncRedis(broker),
        )
        for i in range(150):
            stream2._enqueue_video(f"pkt-{i}".encode("utf-8"))
        assert stream2._video_queue.qsize() == scrcpy_relay._REMOTE_VIDEO_QUEUE_MAXSIZE
        first_kept = await stream2.recv_chunk(timeout=0.1)
        assert first_kept == b"pkt-30"
        await stream2.close()

    asyncio.run(scenario())


def test_binary_redis_factories_create_valid_pubsub_without_encoding_error():
    sync_client = scrcpy_relay._create_sync_binary_redis()
    async_client = scrcpy_relay._create_async_binary_redis()
    try:
        sync_ps = sync_client.pubsub()
        async_ps = async_client.pubsub()
        assert sync_ps is not None
        assert async_ps is not None
        sync_ps.close()
    finally:
        sync_client.close()
        asyncio.run(async_client.aclose())
