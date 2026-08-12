"""Redis control plane for an optional independent Web recording worker.

The browser and Playwright objects remain inside the recorder worker process.  The
API only sends JSON commands and receives short-lived JSON replies, while Redis
stores worker heartbeats and session ownership metadata.  This keeps the default
Windows ``local`` mode unchanged and makes ``worker`` mode safe across multiple
API replicas without pretending that a browser object can be serialized.
"""

from __future__ import annotations

import asyncio
import base64
import contextlib
import json
import os
import socket
import time
import uuid
from typing import Any

from redis.exceptions import RedisError

from app.core import redis_client as _redis_client
from app.core.config import settings


def get_async_redis(db: int = 2) -> Any:
    """Resolve the Redis factory lazily so optional test stubs remain isolated."""
    factory = getattr(_redis_client, "get_async_redis", None)
    if factory is None:
        raise WebRecordingTransportError("Web 录制 Redis 客户端不可用")
    return factory(db)


class WebRecordingTransportError(RuntimeError):
    """A user-safe error raised when the remote recording control plane fails."""

    def __init__(self, detail: str, status_code: int = 503) -> None:
        super().__init__(detail)
        self.detail = detail
        self.status_code = status_code


def _prefix() -> str:
    value = settings.WEB_RECORDER_WORKER_QUEUE_PREFIX.strip()
    return value or "atp:web-recording:commands"


def worker_key(worker_id: str) -> str:
    return f"{_prefix()}:workers:{worker_id}"


def worker_queue_key(worker_id: str) -> str:
    return f"{_prefix()}:{worker_id}"


def response_key(request_id: str) -> str:
    return f"{_prefix()}:replies:{request_id}"


def session_key(session_id: str) -> str:
    return f"{_prefix()}:sessions:{session_id}"


def _json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"))


async def _close_redis(client: Any) -> None:
    close = getattr(_redis_client, "close_async_redis", None)
    if close is not None:
        await close(client)
        return
    close_method = getattr(client, "aclose", None)
    if close_method is not None:
        await close_method()


async def list_recording_workers() -> list[dict[str, Any]]:
    """Return workers whose heartbeat key has not expired."""
    client = get_async_redis()
    try:
        keys = [key async for key in client.scan_iter(match=f"{_prefix()}:workers:*")]
        if not keys:
            return []
        values = await client.mget(keys)
        workers: list[dict[str, Any]] = []
        for value in values:
            if not value:
                continue
            try:
                item = json.loads(value)
            except (TypeError, ValueError, json.JSONDecodeError):
                continue
            if not isinstance(item, dict) or not str(item.get("worker_id") or "").strip():
                continue
            workers.append(item)
        return workers
    except RedisError as exc:
        raise WebRecordingTransportError("录制 Worker 注册中心不可用") from exc
    finally:
        await _close_redis(client)


def _available_workers(workers: list[dict[str, Any]]) -> list[dict[str, Any]]:
    available: list[tuple[int, str, dict[str, Any]]] = []
    for worker in workers:
        try:
            active = max(0, int(worker.get("active_sessions", 0)))
            capacity = max(1, int(worker.get("capacity", 1)))
        except (TypeError, ValueError):
            continue
        worker_id = str(worker.get("worker_id") or "").strip()
        if worker_id and active < capacity:
            available.append((active, worker_id, worker))
    available.sort(key=lambda item: (item[0], item[1]))
    return [item[2] for item in available]


async def choose_recording_worker() -> dict[str, Any]:
    workers = await list_recording_workers()
    available = _available_workers(workers)
    if not available:
        raise WebRecordingTransportError("没有可用的 Web 录制 Worker，请先启动独立录制 Worker", 503)
    return available[0]


async def register_recording_worker(
    worker_id: str,
    *,
    active_sessions: int,
    capacity: int,
    client: Any | None = None,
) -> None:
    owns_client = client is None
    redis = client or get_async_redis()
    try:
        payload = {
            "worker_id": worker_id,
            "active_sessions": max(0, int(active_sessions)),
            "capacity": max(1, int(capacity)),
            "updated_at": time.time(),
            "pid": os.getpid(),
            "hostname": socket.gethostname(),
        }
        ttl = max(5, int(settings.WEB_RECORDER_WORKER_TTL_SECONDS))
        await redis.set(worker_key(worker_id), _json(payload), ex=ttl)
    except RedisError as exc:
        raise WebRecordingTransportError("无法写入 Web 录制 Worker 心跳") from exc
    finally:
        if owns_client:
            await _close_redis(redis)


async def unregister_recording_worker(worker_id: str, *, client: Any | None = None) -> None:
    owns_client = client is None
    redis = client or get_async_redis()
    try:
        await redis.delete(worker_key(worker_id))
    except RedisError:
        # Shutdown should not be held up by a Redis outage.
        pass
    finally:
        if owns_client:
            await _close_redis(redis)


async def save_session_metadata(
    session_id: str,
    *,
    owner_id: int,
    project_id: int,
    worker_id: str,
) -> None:
    client = get_async_redis()
    try:
        payload = {
            "session_id": session_id,
            "owner_id": owner_id,
            "project_id": project_id,
            "worker_id": worker_id,
        }
        ttl = max(60, int(settings.WEB_RECORDER_SESSION_TTL_SECONDS))
        await client.set(session_key(session_id), _json(payload), ex=ttl)
    except RedisError as exc:
        raise WebRecordingTransportError("无法保存 Web 录制会话路由") from exc
    finally:
        await _close_redis(client)


async def load_session_metadata(session_id: str) -> dict[str, Any] | None:
    client = get_async_redis()
    try:
        value = await client.get(session_key(session_id))
        if not value:
            return None
        parsed = json.loads(value)
        return parsed if isinstance(parsed, dict) else None
    except (RedisError, TypeError, ValueError, json.JSONDecodeError) as exc:
        if isinstance(exc, RedisError):
            raise WebRecordingTransportError("无法读取 Web 录制会话路由") from exc
        return None
    finally:
        await _close_redis(client)


async def delete_session_metadata(session_id: str) -> None:
    client = get_async_redis()
    try:
        await client.delete(session_key(session_id))
    except RedisError as exc:
        raise WebRecordingTransportError("无法清理 Web 录制会话路由") from exc
    finally:
        await _close_redis(client)


async def touch_session_metadata(session_id: str) -> None:
    client = get_async_redis()
    try:
        ttl = max(60, int(settings.WEB_RECORDER_SESSION_TTL_SECONDS))
        refreshed = await client.expire(session_key(session_id), ttl)
        if refreshed is False:
            raise WebRecordingTransportError("录制会话已过期", 404)
    except RedisError as exc:
        raise WebRecordingTransportError("无法刷新 Web 录制会话路由") from exc
    finally:
        await _close_redis(client)


async def send_recording_command(worker_id: str, action: str, **payload: Any) -> dict[str, Any]:
    """Queue one command and wait for its short-lived reply."""
    request_id = uuid.uuid4().hex
    reply = response_key(request_id)
    command = {
        "request_id": request_id,
        "reply_key": reply,
        "action": action,
        **payload,
    }
    client = get_async_redis()
    try:
        await client.rpush(worker_queue_key(worker_id), _json(command))
        timeout = max(1, int(settings.WEB_RECORDER_COMMAND_TIMEOUT_SECONDS))
        try:
            result = await asyncio.wait_for(
                client.blpop(reply, timeout=timeout),
                timeout=timeout + 1,
            )
        except asyncio.TimeoutError as exc:
            raise WebRecordingTransportError("Web 录制 Worker 响应超时") from exc
        if not result:
            raise WebRecordingTransportError("Web 录制 Worker 未返回结果")
        try:
            parsed = json.loads(result[1])
        except (TypeError, ValueError, json.JSONDecodeError) as exc:
            raise WebRecordingTransportError("Web 录制 Worker 返回了无效响应") from exc
        return parsed if isinstance(parsed, dict) else {"ok": False, "error": "无效响应"}
    except RedisError as exc:
        raise WebRecordingTransportError("Web 录制 Worker 通道不可用") from exc
    finally:
        with contextlib.suppress(Exception):
            await client.delete(reply)
        with contextlib.suppress(Exception):
            await _close_redis(client)


def _transport_error(
    response: dict[str, Any], *, fallback: str = "Web 录制 Worker 执行失败"
) -> WebRecordingTransportError:
    code = str(response.get("code") or "")
    status = (
        404
        if code == "not_found"
        else 409
        if code in {"busy", "not_ready"}
        else 400
        if code in {"invalid", "start_failed"}
        else 503
    )
    return WebRecordingTransportError(str(response.get("error") or fallback), status)


class RemoteWebRecordingManager:
    """API-side proxy for sessions owned by an independent recorder worker."""

    async def start(self, payload: dict[str, Any], owner_id: int) -> dict[str, Any]:
        worker = await choose_recording_worker()
        session_id = uuid.uuid4().hex
        attempted_worker_ids: set[str] = set()
        response: dict[str, Any] = {}
        worker_id = ""
        while True:
            worker_id = str(worker["worker_id"])
            attempted_worker_ids.add(worker_id)
            response = await send_recording_command(
                worker_id,
                "start",
                session_id=session_id,
                owner_id=owner_id,
                payload=payload,
            )
            if response.get("ok"):
                break

            # The worker is the final authority for its live session count.  A
            # heartbeat can be stale while another API replica is starting a
            # session, so retry only explicit capacity/readiness rejections on
            # another candidate.  Do not retry timeouts or generic failures:
            # the command may have been accepted even if its reply was lost.
            if response.get("code") not in {"busy", "not_ready"}:
                raise _transport_error(response)
            candidates = [
                candidate
                for candidate in _available_workers(await list_recording_workers())
                if str(candidate.get("worker_id") or "") not in attempted_worker_ids
            ]
            if not candidates:
                raise _transport_error(response)
            worker = candidates[0]

        snapshot = response.get("snapshot")
        if not isinstance(snapshot, dict):
            # The worker may already own a live browser even when its reply is
            # malformed.  Stop it before surfacing the protocol error so the
            # next recording is not blocked by an orphaned session.
            with contextlib.suppress(Exception):
                await send_recording_command(worker_id, "stop", session_id=session_id)
            raise WebRecordingTransportError("Web 录制 Worker 未返回会话状态")
        try:
            await save_session_metadata(
                session_id,
                owner_id=owner_id,
                project_id=int(payload["project_id"]),
                worker_id=worker_id,
            )
        except Exception:
            with contextlib.suppress(Exception):
                await send_recording_command(worker_id, "stop", session_id=session_id)
            raise
        return snapshot

    async def _route(self, session_id: str, owner_id: int) -> dict[str, Any]:
        metadata = await load_session_metadata(session_id)
        try:
            metadata_owner = int(metadata.get("owner_id", -1)) if metadata else -1
        except (TypeError, ValueError):
            metadata_owner = -1
        if not metadata or metadata_owner != owner_id:
            raise WebRecordingTransportError("录制会话不存在", 404)
        if not str(metadata.get("worker_id") or "").strip():
            raise WebRecordingTransportError("录制会话路由无效", 503)
        await touch_session_metadata(session_id)
        return metadata

    async def get(self, session_id: str, owner_id: int) -> dict[str, Any]:
        metadata = await self._route(session_id, owner_id)
        response = await send_recording_command(str(metadata["worker_id"]), "snapshot", session_id=session_id)
        if not response.get("ok"):
            if response.get("code") == "not_found":
                await delete_session_metadata(session_id)
            raise _transport_error(response, fallback="无法读取录制会话")
        snapshot = response.get("snapshot")
        if not isinstance(snapshot, dict):
            raise WebRecordingTransportError("录制会话状态无效")
        return snapshot

    async def screenshot(self, session_id: str, owner_id: int) -> bytes:
        metadata = await self._route(session_id, owner_id)
        response = await send_recording_command(str(metadata["worker_id"]), "screenshot", session_id=session_id)
        if not response.get("ok"):
            if response.get("code") == "not_found":
                await delete_session_metadata(session_id)
            raise _transport_error(response, fallback="无法截取录制页面")
        try:
            return base64.b64decode(str(response.get("data") or ""), validate=True)
        except (ValueError, TypeError) as exc:
            raise WebRecordingTransportError("录制 Worker 返回了无效截图") from exc

    async def stop(self, session_id: str, owner_id: int) -> dict[str, Any]:
        metadata = await self._route(session_id, owner_id)
        response = await send_recording_command(str(metadata["worker_id"]), "stop", session_id=session_id)
        if not response.get("ok"):
            if response.get("code") == "not_found":
                await delete_session_metadata(session_id)
            raise _transport_error(response, fallback="无法停止录制会话")
        await delete_session_metadata(session_id)
        snapshot = response.get("snapshot")
        if not isinstance(snapshot, dict):
            raise WebRecordingTransportError("停止录制未返回会话状态")
        return snapshot


def default_worker_id() -> str:
    configured = settings.WEB_RECORDER_WORKER_ID.strip()
    if configured:
        return configured
    return f"{socket.gethostname()}-{os.getpid()}-{uuid.uuid4().hex[:8]}"
