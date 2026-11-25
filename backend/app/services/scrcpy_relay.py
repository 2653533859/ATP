"""Cross-worker Scrcpy H.264 video & control relay built on Redis Pub/Sub (DB 2)."""

from __future__ import annotations

import asyncio
from collections.abc import Callable
from dataclasses import dataclass, field
import json
import logging
import threading
import time
from typing import Any
from uuid import uuid4

import redis
import redis.asyncio as aioredis
from redis.exceptions import RedisError

from app.core.config import settings

logger = logging.getLogger(__name__)

FRAME_VIDEO = 0x01
FRAME_METADATA = 0x02
FRAME_ERROR = 0x03
FRAME_HEARTBEAT = 0x04

_VALID_FRAME_KINDS = frozenset({FRAME_VIDEO, FRAME_METADATA, FRAME_ERROR, FRAME_HEARTBEAT})
_DEFAULT_STREAM_IDLE_TTL_SECONDS = 25.0
_DEFAULT_PING_INTERVAL_SECONDS = 8.0
_DEFAULT_WORKER_HEARTBEAT_SECONDS = 5.0
_DEFAULT_REMOTE_STALL_TIMEOUT_SECONDS = 30.0
_REMOTE_VIDEO_QUEUE_MAXSIZE = 120


class ScrcpyRelayError(RuntimeError):
    """Raised when a cross-worker Scrcpy relay session fails to initialize or continue."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message


def worker_ctrl_channel(worker_id: str) -> str:
    """Return the Redis Pub/Sub channel carrying Backend -> Worker Scrcpy control commands."""
    return f"atp:scrcpy:worker:{worker_id.strip()}:ctrl"


def stream_output_channel(stream_id: str) -> str:
    """Return the Redis Pub/Sub channel carrying Worker -> Backend H.264/metadata frames."""
    return f"atp:scrcpy:stream:{stream_id}"


def stream_ack_channel(request_id: str) -> str:
    """Return the Redis Pub/Sub channel used for synchronous reconnect acknowledgements."""
    return f"atp:scrcpy:ack:{request_id}"


def encode_relay_frame(kind: int, payload: bytes = b"") -> bytes:
    """Encode a relay packet as a 1-byte type header followed by raw binary or UTF-8 payload."""
    if kind not in _VALID_FRAME_KINDS:
        raise ValueError(f"Unsupported relay frame kind: {kind}")
    return bytes((kind,)) + payload


def decode_relay_frame(raw: bytes) -> tuple[int, bytes]:
    """Decode a relay frame produced by encode_relay_frame."""
    if not raw:
        raise ValueError("Empty relay frame")
    kind = raw[0]
    if kind not in _VALID_FRAME_KINDS:
        raise ValueError(f"Unknown relay frame kind: {kind}")
    return kind, raw[1:]


def _decode_json_message(raw_data: Any) -> dict[str, Any] | None:
    if raw_data is None:
        return None
    if isinstance(raw_data, bytes):
        text = raw_data.decode("utf-8", errors="replace")
    elif isinstance(raw_data, str):
        text = raw_data
    else:
        return None
    try:
        parsed = json.loads(text)
    except (TypeError, ValueError, json.JSONDecodeError):
        return None
    return parsed if isinstance(parsed, dict) else None


def _generation_matches(expected_generation: Any, actual_generation: int) -> bool:
    if expected_generation is None:
        return True
    try:
        return int(expected_generation) == int(actual_generation)
    except (TypeError, ValueError):
        return False


def _create_sync_binary_redis() -> redis.Redis:
    return redis.from_url(
        settings.redis_url(2),
        decode_responses=False,
        socket_connect_timeout=5,
        socket_timeout=None,
    )


def _create_async_binary_redis() -> aioredis.Redis:
    return aioredis.from_url(
        settings.redis_url(2),
        decode_responses=False,
        max_connections=20,
        socket_connect_timeout=5,
        socket_timeout=None,
    )


@dataclass
class _WorkerRelaySession:
    stream_id: str
    serial: str
    stream_channel: str
    force_restart: bool = False
    last_ping_at: float = field(default_factory=time.monotonic)
    stop_event: threading.Event = field(default_factory=threading.Event)
    thread: threading.Thread | None = None


class ScrcpyWorkerRelayAgent:
    """Daemon control + streaming relay inside an Android Worker process.

    Runs on dedicated background threads so it never occupies the Worker's single Celery slot.
    """

    def __init__(
        self,
        *,
        worker_id: str,
        instance_generation: int,
        redis_client: Any | None = None,
        redis_factory: Callable[[], Any] | None = None,
        owns_client: bool | None = None,
        manager: Any | None = None,
        idle_ttl_seconds: float = _DEFAULT_STREAM_IDLE_TTL_SECONDS,
        heartbeat_interval_seconds: float = _DEFAULT_WORKER_HEARTBEAT_SECONDS,
    ) -> None:
        self.worker_id = worker_id.strip()
        self.instance_generation = int(instance_generation)
        self._redis = redis_client
        self._redis_factory = redis_factory or _create_sync_binary_redis
        self._owns_client = (redis_client is None) if owns_client is None else bool(owns_client)
        if manager is None:
            from app.device_stream.manager import scrcpy_manager as default_scrcpy_manager

            manager = default_scrcpy_manager
        self._manager: Any = manager
        self.idle_ttl_seconds = float(idle_ttl_seconds)
        self.heartbeat_interval_seconds = float(heartbeat_interval_seconds)
        self._stop_event = threading.Event()
        self._thread: threading.Thread | None = None
        self._pubsub: Any | None = None
        self._sessions_lock = threading.Lock()
        self._sessions: dict[str, _WorkerRelaySession] = {}

    def _client(self) -> Any:
        if self._redis is None:
            self._redis = self._redis_factory()
        return self._redis

    def _publish_frame(self, channel: str, kind: int, payload: bytes = b"") -> None:
        self._client().publish(channel, encode_relay_frame(kind, payload))

    def _publish_json_frame(self, channel: str, kind: int, payload: dict[str, Any]) -> None:
        encoded = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self._publish_frame(channel, kind, encoded)

    def _publish_error(self, channel: str, code: str, message: str) -> None:
        try:
            self._publish_json_frame(channel, FRAME_ERROR, {"code": code, "message": message})
        except Exception:
            logger.debug("Failed to publish Scrcpy relay error on %s", channel, exc_info=True)

    def _handle_reconnect(self, serial: str, request_id: str, *, force: bool) -> None:
        ack_channel = stream_ack_channel(request_id) if request_id else ""
        try:
            if force and hasattr(self._manager, "_cleanup_device"):
                self._manager._cleanup_device(serial)
            dev_info = self._manager.ensure_device_stream(serial)
            payload: dict[str, Any] = {
                "ok": True,
                "serial": serial,
                "width": int(getattr(dev_info, "screen_width", 0) or 0),
                "height": int(getattr(dev_info, "screen_height", 0) or 0),
                "device_name": str(getattr(dev_info, "device_name", "") or ""),
            }
        except Exception as exc:
            logger.warning("Worker Scrcpy reconnect failed for %s: %s", serial, exc)
            payload = {"ok": False, "serial": serial, "error": str(exc)}

        if ack_channel:
            try:
                self._client().publish(ack_channel, json.dumps(payload, ensure_ascii=False).encode("utf-8"))
            except Exception:
                logger.debug("Failed to publish Scrcpy reconnect ack on %s", ack_channel, exc_info=True)

    def _run_session(self, session: _WorkerRelaySession) -> None:
        stream: Any | None = None
        try:
            if session.force_restart:
                with self._sessions_lock:
                    other_active = any(
                        s.stream_id != session.stream_id and s.serial == session.serial and not s.stop_event.is_set()
                        for s in self._sessions.values()
                    )
                if not other_active and hasattr(self._manager, "_cleanup_device"):
                    self._manager._cleanup_device(session.serial)

            stream = self._manager.create_client_stream(session.serial)
            dev_info = getattr(stream, "dev_info", None)
            metadata = {
                "serial": session.serial,
                "width": int(getattr(dev_info, "screen_width", 0) or 0),
                "height": int(getattr(dev_info, "screen_height", 0) or 0),
                "device_name": str(getattr(dev_info, "device_name", "") or ""),
            }
            self._publish_json_frame(session.stream_channel, FRAME_METADATA, metadata)

            last_heartbeat_at = time.monotonic()
            while not self._stop_event.is_set() and not session.stop_event.is_set():
                chunk = stream.get_chunk(timeout=0.5)
                if chunk is None:
                    if not session.stop_event.is_set() and not self._stop_event.is_set():
                        err_reason = getattr(dev_info, "error", None) or "Scrcpy 视频流已结束"
                        self._publish_error(session.stream_channel, "stream_ended", str(err_reason))
                    break
                if chunk:
                    self._publish_frame(session.stream_channel, FRAME_VIDEO, chunk)
                    last_heartbeat_at = time.monotonic()
                elif time.monotonic() - last_heartbeat_at >= self.heartbeat_interval_seconds:
                    self._publish_frame(session.stream_channel, FRAME_HEARTBEAT)
                    last_heartbeat_at = time.monotonic()
        except Exception as exc:
            if not session.stop_event.is_set() and not self._stop_event.is_set():
                logger.warning("Scrcpy relay session failed for %s (%s): %s", session.serial, session.stream_id, exc)
                self._publish_error(session.stream_channel, "scrcpy_start_failed", str(exc))
        finally:
            if stream is not None:
                try:
                    stream.close()
                except Exception:
                    pass
            with self._sessions_lock:
                self._sessions.pop(session.stream_id, None)

    def _reap_expired_sessions(self) -> None:
        now = time.monotonic()
        with self._sessions_lock:
            expired = [
                session for session in self._sessions.values() if now - session.last_ping_at > self.idle_ttl_seconds
            ]
        for session in expired:
            logger.info("Closing stale Scrcpy relay session %s (%s)", session.stream_id, session.serial)
            session.stop_event.set()

    def process_control_message(self, payload: dict[str, Any]) -> None:
        """Handle a single control JSON message sent from Backend to this Worker."""
        cmd_type = str(payload.get("type") or "").strip().lower()
        stream_id = str(payload.get("stream_id") or "").strip()
        serial = str(payload.get("serial") or "").strip()
        expected_generation = payload.get("expected_generation")

        if not _generation_matches(expected_generation, self.instance_generation):
            if cmd_type == "start" and stream_id:
                self._publish_error(
                    stream_output_channel(stream_id),
                    "worker_generation_mismatch",
                    "Worker 实例如已重启，当前代数与期望不匹配",
                )
            elif cmd_type == "reconnect":
                req_id = str(payload.get("request_id") or "").strip()
                if req_id:
                    try:
                        self._client().publish(
                            stream_ack_channel(req_id),
                            json.dumps(
                                {"ok": False, "error": "worker_generation_mismatch: Worker 实例代数已变化"},
                                ensure_ascii=False,
                            ).encode("utf-8"),
                        )
                    except Exception:
                        pass
            return

        if cmd_type == "start":
            if not stream_id or not serial:
                return
            session = _WorkerRelaySession(
                stream_id=stream_id,
                serial=serial,
                stream_channel=stream_output_channel(stream_id),
                force_restart=bool(payload.get("force_restart")),
            )
            with self._sessions_lock:
                old = self._sessions.pop(stream_id, None)
                if old is not None:
                    old.stop_event.set()
                self._sessions[stream_id] = session
            thread = threading.Thread(
                target=self._run_session,
                args=(session,),
                name=f"atp-scrcpy-stream-{stream_id[:8]}",
                daemon=True,
            )
            session.thread = thread
            thread.start()
            return

        if cmd_type == "ping":
            if stream_id:
                with self._sessions_lock:
                    existing_session = self._sessions.get(stream_id)
                    if existing_session is not None:
                        existing_session.last_ping_at = time.monotonic()
            return

        if cmd_type == "stop":
            if stream_id:
                with self._sessions_lock:
                    existing_session = self._sessions.get(stream_id)
                    if existing_session is not None:
                        existing_session.stop_event.set()
            return

        if cmd_type == "reconnect":
            if not serial:
                return
            req_id = str(payload.get("request_id") or "").strip()
            force = bool(payload.get("force", True))
            threading.Thread(
                target=self._handle_reconnect,
                args=(serial, req_id),
                kwargs={"force": force},
                name=f"atp-scrcpy-reconnect-{serial[:12]}",
                daemon=True,
            ).start()
            return

        if not serial:
            return

        try:
            if cmd_type == "touch":
                self._manager.send_touch_event(
                    serial,
                    int(payload.get("action", 0)),
                    int(payload.get("x", 0)),
                    int(payload.get("y", 0)),
                    payload.get("w"),
                    payload.get("h"),
                )
            elif cmd_type == "key":
                self._manager.send_key_event(serial, int(payload.get("keycode", 0)))
            elif cmd_type == "text":
                self._manager.send_text_event(serial, str(payload.get("text", "")))
        except Exception as exc:
            logger.debug("Ignored Scrcpy relay control command %s for %s: %s", cmd_type, serial, exc)

    def _control_loop(self) -> None:
        channel = worker_ctrl_channel(self.worker_id)
        pubsub: Any | None = None
        while not self._stop_event.is_set():
            try:
                if pubsub is None:
                    pubsub = self._client().pubsub()
                    self._pubsub = pubsub
                    pubsub.subscribe(channel)
                    logger.info("Scrcpy worker relay subscribed to %s", channel)

                msg = pubsub.get_message(ignore_subscribe_messages=True, timeout=0.5)
                if msg and msg.get("type") == "message":
                    parsed = _decode_json_message(msg.get("data"))
                    if parsed is not None:
                        self.process_control_message(parsed)
                elif msg is None:
                    # Keep fake in-memory pubsubs from tight-spinning in tests
                    self._stop_event.wait(0.02)

                self._reap_expired_sessions()
            except RedisError as exc:
                if self._stop_event.is_set():
                    break
                logger.warning("Scrcpy relay Redis error on %s, retrying: %s", channel, exc)
                if pubsub is not None:
                    try:
                        pubsub.close()
                    except Exception:
                        pass
                    pubsub = None
                    self._pubsub = None
                self._stop_event.wait(1.0)
            except Exception:
                if self._stop_event.is_set():
                    break
                logger.exception("Unexpected error in Scrcpy worker relay control loop")
                self._stop_event.wait(0.5)

        if pubsub is not None:
            try:
                pubsub.close()
            except Exception:
                pass
            self._pubsub = None

    def start(self) -> None:
        """Start the background Scrcpy relay daemon thread."""
        if not self.worker_id:
            return
        if self._thread is not None and self._thread.is_alive():
            return
        self._stop_event.clear()
        self._thread = threading.Thread(
            target=self._control_loop,
            name=f"atp-scrcpy-relay-{self.worker_id}",
            daemon=True,
        )
        self._thread.start()

    def stop(self, timeout: float = 5.0) -> None:
        """Stop all active relay sessions, clean up Scrcpy devices, and close Redis resources."""
        self._stop_event.set()
        with self._sessions_lock:
            sessions = list(self._sessions.values())
        for session in sessions:
            session.stop_event.set()

        for session in sessions:
            if session.thread is not None:
                session.thread.join(timeout=min(timeout, 2.0))

        if self._pubsub is not None:
            try:
                self._pubsub.close()
            except Exception:
                pass
            self._pubsub = None

        if self._thread is not None:
            self._thread.join(timeout=timeout)
            self._thread = None

        try:
            self._manager.cleanup_all()
        except Exception:
            logger.debug("Scrcpy manager cleanup_all failed during worker stop", exc_info=True)

        if self._owns_client and self._redis is not None:
            try:
                self._redis.close()
            except Exception:
                pass
            self._redis = None


class RemoteScrcpyStream:
    """Async Backend consumer for one Worker-hosted Scrcpy video/control stream."""

    def __init__(
        self,
        *,
        worker_id: str,
        serial: str,
        expected_generation: int | None = None,
        redis_client: Any | None = None,
        redis_factory: Callable[[], Any] | None = None,
        owns_client: bool | None = None,
        ping_interval_seconds: float = _DEFAULT_PING_INTERVAL_SECONDS,
        stall_timeout_seconds: float = _DEFAULT_REMOTE_STALL_TIMEOUT_SECONDS,
    ) -> None:
        self.worker_id = worker_id.strip()
        self.serial = serial
        self.expected_generation = expected_generation
        self.stream_id = uuid4().hex
        self.ctrl_channel = worker_ctrl_channel(self.worker_id)
        self.stream_channel = stream_output_channel(self.stream_id)
        self._redis = redis_client
        self._redis_factory = redis_factory or _create_async_binary_redis
        self._owns_client = (redis_client is None) if owns_client is None else bool(owns_client)
        self.ping_interval_seconds = float(ping_interval_seconds)
        self.stall_timeout_seconds = float(stall_timeout_seconds)

        self._pubsub: Any | None = None
        self._video_queue: asyncio.Queue[bytes | None] = asyncio.Queue(maxsize=_REMOTE_VIDEO_QUEUE_MAXSIZE)
        self._ready_event = asyncio.Event()
        self._reader_task: asyncio.Task[None] | None = None
        self._ping_task: asyncio.Task[None] | None = None
        self._closed = False
        self._last_activity = time.monotonic()
        self.metadata: dict[str, Any] = {}
        self.error_code: str | None = None
        self.error_message: str | None = None

    def _client(self) -> Any:
        if self._redis is None:
            self._redis = self._redis_factory()
        return self._redis

    async def _publish_ctrl(self, payload: dict[str, Any]) -> None:
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        await self._client().publish(self.ctrl_channel, body)

    def _enqueue_video(self, chunk: bytes | None) -> None:
        if chunk is None:
            while self._video_queue.full():
                try:
                    self._video_queue.get_nowait()
                except asyncio.QueueEmpty:
                    break
            self._video_queue.put_nowait(None)
            return

        if self._video_queue.full():
            try:
                self._video_queue.get_nowait()
            except asyncio.QueueEmpty:
                pass
        try:
            self._video_queue.put_nowait(chunk)
        except asyncio.QueueFull:
            pass

    async def _read_loop(self) -> None:
        assert self._pubsub is not None
        try:
            while not self._closed:
                t0 = time.monotonic()
                msg = await self._pubsub.get_message(ignore_subscribe_messages=True, timeout=0.5)
                if msg and msg.get("type") == "message":
                    raw = msg.get("data")
                    if not isinstance(raw, (bytes, bytearray)):
                        continue
                    try:
                        kind, payload = decode_relay_frame(bytes(raw))
                    except ValueError:
                        continue
                    self._last_activity = time.monotonic()

                    if kind == FRAME_VIDEO:
                        self._enqueue_video(payload)
                        self._ready_event.set()
                    elif kind == FRAME_METADATA:
                        parsed = _decode_json_message(payload)
                        if parsed is not None:
                            self.metadata = parsed
                        self._ready_event.set()
                    elif kind == FRAME_HEARTBEAT:
                        continue
                    elif kind == FRAME_ERROR:
                        parsed = _decode_json_message(payload) or {}
                        self.error_code = str(parsed.get("code") or "relay_error")
                        self.error_message = str(parsed.get("message") or "Scrcpy 中继视频流异常结束")
                        self._ready_event.set()
                        break
                else:
                    if time.monotonic() - self._last_activity > self.stall_timeout_seconds:
                        self.error_code = "worker_stream_stalled"
                        self.error_message = f"节点 '{self.worker_id}' 视频流心跳超时"
                        self._ready_event.set()
                        break
                    if time.monotonic() - t0 < 0.02:
                        await asyncio.sleep(0.02)
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            if not self._closed:
                logger.warning("Remote Scrcpy reader loop failed (%s/%s): %s", self.worker_id, self.serial, exc)
                self.error_code = self.error_code or "relay_connection_lost"
                self.error_message = self.error_message or str(exc)
                self._ready_event.set()
        finally:
            self._enqueue_video(None)

    async def _ping_loop(self) -> None:
        try:
            while not self._closed:
                await asyncio.sleep(self.ping_interval_seconds)
                if self._closed:
                    break
                await self._publish_ctrl(
                    {
                        "type": "ping",
                        "stream_id": self.stream_id,
                        "serial": self.serial,
                        "expected_generation": self.expected_generation,
                    }
                )
        except asyncio.CancelledError:
            raise
        except Exception:
            logger.debug("Scrcpy relay ping stopped for %s", self.stream_id, exc_info=True)

    async def start(self, *, force_restart: bool = False, ready_timeout: float = 15.0) -> None:
        """Subscribe to stream frames, request Worker start, and await readiness/metadata."""
        client = self._client()
        self._pubsub = client.pubsub()
        await self._pubsub.subscribe(self.stream_channel)
        self._last_activity = time.monotonic()
        self._reader_task = asyncio.create_task(self._read_loop())
        self._ping_task = asyncio.create_task(self._ping_loop())

        await self._publish_ctrl(
            {
                "type": "start",
                "stream_id": self.stream_id,
                "serial": self.serial,
                "expected_generation": self.expected_generation,
                "force_restart": force_restart,
            }
        )

        try:
            await asyncio.wait_for(self._ready_event.wait(), timeout=ready_timeout)
        except TimeoutError as exc:
            await self.close()
            raise ScrcpyRelayError(
                "relay_start_timeout",
                f"等待节点 '{self.worker_id}' 启动 Scrcpy 视频流超时",
            ) from exc

        if self.error_code:
            code = self.error_code
            msg = self.error_message or "Scrcpy 启动失败"
            await self.close()
            raise ScrcpyRelayError(code, msg)

    async def recv_chunk(self, timeout: float = 1.0) -> bytes | None:
        """Return next H.264 chunk, b'' on idle tick, or None when the stream ends."""
        if self._closed and self._video_queue.empty():
            return None
        try:
            chunk = await asyncio.wait_for(self._video_queue.get(), timeout=timeout)
        except TimeoutError:
            return None if self._closed else b""
        return chunk

    async def send_touch(self, action: int, x: int, y: int, width: int | None, height: int | None) -> None:
        if self._closed:
            return
        await self._publish_ctrl(
            {
                "type": "touch",
                "stream_id": self.stream_id,
                "serial": self.serial,
                "action": int(action),
                "x": int(x),
                "y": int(y),
                "w": width,
                "h": height,
                "expected_generation": self.expected_generation,
            }
        )

    async def send_key(self, keycode: int) -> None:
        if self._closed:
            return
        await self._publish_ctrl(
            {
                "type": "key",
                "stream_id": self.stream_id,
                "serial": self.serial,
                "keycode": int(keycode),
                "expected_generation": self.expected_generation,
            }
        )

    async def send_text(self, text: str) -> None:
        if self._closed:
            return
        await self._publish_ctrl(
            {
                "type": "text",
                "stream_id": self.stream_id,
                "serial": self.serial,
                "text": text,
                "expected_generation": self.expected_generation,
            }
        )

    async def close(self) -> None:
        """Stop background loops, tell Worker to end the session, and close Redis handles."""
        if self._closed:
            return
        self._closed = True
        self._enqueue_video(None)

        for task in (self._ping_task, self._reader_task):
            if task is not None and not task.done():
                task.cancel()
        for task in (self._ping_task, self._reader_task):
            if task is not None:
                try:
                    await task
                except (asyncio.CancelledError, Exception):
                    pass
        self._ping_task = None
        self._reader_task = None

        if self._redis is not None:
            try:
                await self._publish_ctrl(
                    {
                        "type": "stop",
                        "stream_id": self.stream_id,
                        "serial": self.serial,
                        "expected_generation": self.expected_generation,
                    }
                )
            except Exception:
                pass

        if self._pubsub is not None:
            try:
                await self._pubsub.unsubscribe(self.stream_channel)
            except Exception:
                pass
            await _close_async_resource(self._pubsub)
            self._pubsub = None

        if self._owns_client and self._redis is not None:
            await _close_async_resource(self._redis)
            self._redis = None


async def _close_async_resource(resource: Any) -> None:
    """Close an async Redis client or pubsub handle without assuming aclose vs close."""
    close_fn = getattr(resource, "aclose", None) or getattr(resource, "close", None)
    if callable(close_fn):
        try:
            await close_fn()
        except Exception:
            pass


async def open_remote_scrcpy_stream(
    worker_id: str,
    serial: str,
    *,
    expected_generation: int | None = None,
    force_restart: bool = False,
    ready_timeout: float = 15.0,
    redis_client: Any | None = None,
    redis_factory: Callable[[], Any] | None = None,
) -> RemoteScrcpyStream:
    """Open and initialize a remote Worker-hosted Scrcpy stream."""
    session = RemoteScrcpyStream(
        worker_id=worker_id,
        serial=serial,
        expected_generation=expected_generation,
        redis_client=redis_client,
        redis_factory=redis_factory,
    )
    await session.start(force_restart=force_restart, ready_timeout=ready_timeout)
    return session


async def request_remote_scrcpy_reconnect(
    worker_id: str,
    serial: str,
    *,
    expected_generation: int | None = None,
    force: bool = True,
    timeout: float = 15.0,
    redis_client: Any | None = None,
    redis_factory: Callable[[], Any] | None = None,
) -> dict[str, Any]:
    """Ask an Android Worker to restart/ensure its Scrcpy stream and wait for the acknowledgement."""
    owns_client = redis_client is None
    client: Any = redis_client if redis_client is not None else (redis_factory or _create_async_binary_redis)()
    request_id = uuid4().hex
    ack_chan = stream_ack_channel(request_id)
    pubsub: Any = client.pubsub()
    try:
        await pubsub.subscribe(ack_chan)
        await client.publish(
            worker_ctrl_channel(worker_id),
            json.dumps(
                {
                    "type": "reconnect",
                    "request_id": request_id,
                    "serial": serial,
                    "expected_generation": expected_generation,
                    "force": force,
                },
                ensure_ascii=False,
            ).encode("utf-8"),
        )
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            t0 = time.monotonic()
            msg = await pubsub.get_message(ignore_subscribe_messages=True, timeout=0.5)
            if msg and msg.get("type") == "message":
                parsed = _decode_json_message(msg.get("data"))
                if parsed is not None:
                    if not parsed.get("ok"):
                        raise ScrcpyRelayError(
                            "scrcpy_reconnect_failed",
                            str(parsed.get("error") or "Worker 重连 Scrcpy 失败"),
                        )
                    return parsed
            elif time.monotonic() - t0 < 0.02:
                await asyncio.sleep(0.02)
        raise ScrcpyRelayError("scrcpy_reconnect_timeout", f"等待节点 '{worker_id}' 重连 Scrcpy 超时")
    finally:
        try:
            await pubsub.unsubscribe(ack_chan)
        except Exception:
            pass
        await _close_async_resource(pubsub)
        if owns_client:
            await _close_async_resource(client)
