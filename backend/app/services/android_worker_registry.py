"""Redis registry for Windows Android Worker heartbeats.

The API process cannot inspect a user's local ``adb`` installation directly when
the backend is deployed on a public host.  The Windows Worker therefore keeps a
short-lived Redis record while it is alive.  Expiration is intentional: a
crashed or disconnected Worker disappears without requiring a database cleanup
job.
"""

from __future__ import annotations

import json
import os
import socket
import time
from typing import Any

from redis.exceptions import RedisError

from app.core import redis_client as _redis_client
from app.core.config import settings


class AndroidWorkerRegistryError(RuntimeError):
    """Raised when the Android Worker registry cannot be read or written."""


def _prefix() -> str:
    value = settings.ANDROID_WORKER_REGISTRY_PREFIX.strip()
    return value or "atp:android-worker"


def worker_key(worker_id: str) -> str:
    return f"{_prefix()}:workers:{worker_id}"


def worker_queue() -> str:
    return settings.ANDROID_WORKER_QUEUE.strip() or "mobile_special"


def _json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"))


def _decode(value: Any) -> Any:
    if isinstance(value, bytes):
        return value.decode("utf-8", errors="replace")
    return value


def _redis() -> Any:
    factory = getattr(_redis_client, "get_async_redis", None)
    if factory is None:
        raise AndroidWorkerRegistryError("Android Worker Redis 客户端不可用")
    return factory()


async def _close(redis: Any) -> None:
    close = getattr(_redis_client, "close_async_redis", None)
    if close is not None:
        await close(redis)
        return
    close_method = getattr(redis, "aclose", None)
    if close_method is not None:
        await close_method()


def build_worker_payload(worker_id: str, *, queues: list[str] | None = None) -> dict[str, Any]:
    now = time.time()
    ttl = max(5, int(settings.ANDROID_WORKER_TTL_SECONDS))
    return {
        "worker_id": worker_id,
        "status": "online",
        "queues": queues or [worker_queue()],
        "capabilities": ["adb", "android"],
        "hostname": socket.gethostname(),
        "pid": os.getpid(),
        "updated_at": now,
        "expires_at": now + ttl,
    }


async def register_android_worker(
    worker_id: str,
    *,
    queues: list[str] | None = None,
    client: Any | None = None,
) -> dict[str, Any]:
    """Refresh one Worker record and return the payload written to Redis."""

    normalized_id = worker_id.strip()
    if not normalized_id:
        raise AndroidWorkerRegistryError("Android Worker ID 不能为空")
    owns_client = client is None
    redis = client or _redis()
    payload = build_worker_payload(normalized_id, queues=queues)
    try:
        await redis.set(
            worker_key(normalized_id),
            _json(payload),
            ex=max(5, int(settings.ANDROID_WORKER_TTL_SECONDS)),
        )
        return payload
    except RedisError as exc:
        raise AndroidWorkerRegistryError("无法写入 Android Worker 心跳") from exc
    finally:
        if owns_client:
            await _close(redis)


async def unregister_android_worker(worker_id: str, *, client: Any | None = None) -> None:
    """Remove a Worker record during a graceful shutdown."""

    normalized_id = worker_id.strip()
    if not normalized_id:
        return
    owns_client = client is None
    redis = client or _redis()
    try:
        await redis.delete(worker_key(normalized_id))
    except RedisError:
        # Shutdown must not hang because Redis is already unavailable.
        return
    finally:
        if owns_client:
            await _close(redis)


async def list_android_workers() -> list[dict[str, Any]]:
    """List currently live Android Workers from the TTL-backed registry."""

    redis = _redis()
    try:
        keys = [key async for key in redis.scan_iter(match=f"{_prefix()}:workers:*")]
        if not keys:
            return []
        values = await redis.mget(keys)
        workers: list[dict[str, Any]] = []
        for value in values:
            raw = _decode(value)
            if not raw:
                continue
            try:
                item = json.loads(raw)
            except (TypeError, ValueError, json.JSONDecodeError):
                continue
            if not isinstance(item, dict) or not str(item.get("worker_id") or "").strip():
                continue
            workers.append(item)
        workers.sort(key=lambda item: str(item.get("worker_id") or ""))
        return workers
    except RedisError as exc:
        raise AndroidWorkerRegistryError("Android Worker 注册中心不可用") from exc
    finally:
        await _close(redis)
