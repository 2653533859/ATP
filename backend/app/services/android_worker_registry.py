"""Redis registry for Windows Android Worker heartbeats.

The API process cannot inspect a user's local ``adb`` installation directly when
the backend is deployed on a public host.  The Windows Worker therefore keeps a
short-lived Redis record while it is alive.  Expiration is intentional: a
crashed or disconnected Worker disappears without requiring a database cleanup
job.
"""

from __future__ import annotations

import json
import logging
import os
import re
import shutil
import socket
import threading
import time
from typing import Any, Callable
from uuid import uuid4

from redis.exceptions import RedisError

from app.core import redis_client as _redis_client
from app.core.config import settings

logger = logging.getLogger(__name__)

WORKER_ID_PATTERN = re.compile(r"^[a-zA-Z0-9][a-zA-Z0-9._-]{0,63}$")

_RENEW_IF_TOKEN_MATCHES_LUA = """
local current = redis.call('GET', KEYS[1])
if not current then
  return 0
end
local ok, decoded = pcall(cjson.decode, current)
if ok and type(decoded) == 'table' and decoded['instance_token'] == ARGV[1] then
  redis.call('SET', KEYS[1], ARGV[2], 'EX', tonumber(ARGV[3]))
  return 1
end
return 0
"""

_RELEASE_IF_TOKEN_MATCHES_LUA = """
local current = redis.call('GET', KEYS[1])
if not current then
  return 1
end
local ok, decoded = pcall(cjson.decode, current)
if ok and type(decoded) == 'table' and decoded['instance_token'] == ARGV[1] then
  return redis.call('DEL', KEYS[1])
end
return 0
"""


class AndroidWorkerRegistryError(RuntimeError):
    """Raised when the Android Worker registry cannot be read or written."""


class AndroidWorkerConflictError(AndroidWorkerRegistryError):
    """Raised when a worker_id is already claimed by another live instance."""


def normalize_worker_id(worker_id: str) -> str:
    """Validate and normalize a persistent Android Worker ID."""
    normalized = str(worker_id or "").strip()
    if not WORKER_ID_PATTERN.fullmatch(normalized):
        raise AndroidWorkerRegistryError(
            "Android Worker ID 无效：需为 1~64 位字母、数字、点、下划线或短横线，且以字母或数字开头"
        )
    return normalized


def worker_android_queue(worker_id: str) -> str:
    """Return the dedicated Android scan/case queue for one worker."""
    return f"android.{normalize_worker_id(worker_id)}"


def worker_execution_queue(worker_id: str, base: str | None = None) -> str:
    """Return the dedicated device-operation/special queue for one worker."""
    prefix = (base or settings.ANDROID_WORKER_QUEUE or "mobile_special").strip() or "mobile_special"
    return f"{prefix}.{normalize_worker_id(worker_id)}"


def worker_queues_for(worker_id: str, *, multi_node: bool | None = None) -> list[str]:
    """Return the Celery queues owned by a worker in current mode."""
    use_multi = settings.ANDROID_MULTI_NODE_ENABLED if multi_node is None else multi_node
    exec_base = settings.ANDROID_WORKER_QUEUE.strip() or "mobile_special"
    if use_multi:
        return [worker_android_queue(worker_id), worker_execution_queue(worker_id, exec_base)]
    return ["android", exec_base]


def generate_instance_identity() -> tuple[int, str]:
    """Generate a monotonic-like generation number and random instance token."""
    return time.time_ns() // 1_000_000, uuid4().hex


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
    try:
        return factory()
    except RuntimeError as exc:
        raise AndroidWorkerRegistryError("Android Worker Redis 客户端不可用") from exc


async def _close(redis: Any) -> None:
    close = getattr(_redis_client, "close_async_redis", None)
    if close is not None:
        await close(redis)
        return
    close_method = getattr(redis, "aclose", None)
    if close_method is not None:
        await close_method()


def build_worker_payload(
    worker_id: str,
    *,
    queues: list[str] | None = None,
    instance_generation: int | None = None,
    instance_token: str | None = None,
    adb_ok: bool = True,
    busy: bool = False,
) -> dict[str, Any]:
    now = time.time()
    ttl = max(5, int(settings.ANDROID_WORKER_TTL_SECONDS))
    payload: dict[str, Any] = {
        "worker_id": worker_id,
        "status": "online",
        "queues": queues or [worker_queue()],
        "capabilities": ["adb", "android"],
        "hostname": socket.gethostname(),
        "pid": os.getpid(),
        "adb_ok": bool(adb_ok),
        "busy": bool(busy),
        "updated_at": now,
        "expires_at": now + ttl,
    }
    if instance_generation is not None:
        payload["instance_generation"] = int(instance_generation)
    if instance_token:
        payload["instance_token"] = str(instance_token)
    return payload


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
    runtime_gen = get_current_worker_generation() if get_current_worker_id() == normalized_id else None
    runtime_tok = get_current_worker_token() if get_current_worker_id() == normalized_id else ""
    payload = build_worker_payload(
        normalized_id,
        queues=queues,
        instance_generation=runtime_gen,
        instance_token=runtime_tok or None,
        busy=is_slot_busy(),
    )
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


async def get_android_worker(worker_id: str) -> dict[str, Any] | None:
    """Fetch one live Android Worker record from Redis, or None if offline."""
    normalized_id = worker_id.strip()
    if not normalized_id:
        return None
    redis = _redis()
    try:
        raw = _decode(await redis.get(worker_key(normalized_id)))
        if not raw:
            return None
        item = json.loads(raw)
        return item if isinstance(item, dict) else None
    except (TypeError, ValueError, json.JSONDecodeError):
        return None
    except RedisError as exc:
        raise AndroidWorkerRegistryError("Android Worker 注册中心不可用") from exc
    finally:
        await _close(redis)


def _sync_redis_client() -> Any:
    import redis

    timeout = settings.REDIS_CONNECT_TIMEOUT_SECONDS
    return redis.from_url(
        settings.redis_url(2),
        decode_responses=True,
        socket_connect_timeout=timeout,
        socket_timeout=timeout,
    )


def claim_android_worker_sync(
    redis_client: Any,
    worker_id: str,
    *,
    instance_generation: int,
    instance_token: str,
    queues: list[str] | None = None,
    ttl_seconds: int | None = None,
    adb_ok: bool = True,
    busy: bool = False,
) -> dict[str, Any]:
    """Atomically claim a worker_id slot; fail if another live instance owns it."""
    normalized_id = normalize_worker_id(worker_id)
    ttl = max(5, int(ttl_seconds or settings.ANDROID_WORKER_TTL_SECONDS))
    payload = build_worker_payload(
        normalized_id,
        queues=queues or worker_queues_for(normalized_id),
        instance_generation=instance_generation,
        instance_token=instance_token,
        adb_ok=adb_ok,
        busy=busy,
    )
    key = worker_key(normalized_id)
    acquired = redis_client.set(key, _json(payload), ex=ttl, nx=True)
    if acquired:
        return payload

    raw = _decode(redis_client.get(key))
    if raw:
        try:
            existing = json.loads(raw)
            if isinstance(existing, dict) and existing.get("instance_token") == instance_token:
                redis_client.set(key, _json(payload), ex=ttl)
                return payload
        except (TypeError, ValueError, json.JSONDecodeError):
            pass
    raise AndroidWorkerConflictError(f"Android Worker ID '{normalized_id}' 已被另一个在线实例占用")


def renew_android_worker_sync(
    redis_client: Any,
    worker_id: str,
    *,
    instance_generation: int,
    instance_token: str,
    queues: list[str] | None = None,
    ttl_seconds: int | None = None,
    adb_ok: bool = True,
    busy: bool = False,
) -> bool:
    """Renew worker heartbeat only if token still matches a live record."""
    normalized_id = normalize_worker_id(worker_id)
    ttl = max(5, int(ttl_seconds or settings.ANDROID_WORKER_TTL_SECONDS))
    payload = build_worker_payload(
        normalized_id,
        queues=queues or worker_queues_for(normalized_id),
        instance_generation=instance_generation,
        instance_token=instance_token,
        adb_ok=adb_ok,
        busy=busy,
    )
    key = worker_key(normalized_id)
    raw_json = _json(payload)
    if hasattr(redis_client, "eval"):
        result = redis_client.eval(_RENEW_IF_TOKEN_MATCHES_LUA, 1, key, instance_token, raw_json, str(ttl))
        return bool(int(result or 0))
    if hasattr(redis_client, "get"):
        raw_current = _decode(redis_client.get(key))
        if not raw_current:
            return False
        try:
            current = json.loads(raw_current)
        except (TypeError, ValueError, json.JSONDecodeError):
            return False
        if not isinstance(current, dict) or current.get("instance_token") != instance_token:
            return False
    return bool(redis_client.set(key, raw_json, ex=ttl))


def release_android_worker_sync(redis_client: Any, worker_id: str, *, instance_token: str) -> None:
    """Release worker slot on graceful shutdown if token still matches."""
    normalized_id = worker_id.strip()
    if not normalized_id:
        return
    key = worker_key(normalized_id)
    if hasattr(redis_client, "eval"):
        redis_client.eval(_RELEASE_IF_TOKEN_MATCHES_LUA, 1, key, instance_token)
    else:
        redis_client.delete(key)


def acquire_worker_scan_lock_sync(redis_client: Any, worker_id: str, *, ttl_seconds: int = 60) -> str | None:
    """Acquire a short cross-process scan lock for one worker to prevent out-of-order commits."""
    normalized_id = normalize_worker_id(worker_id)
    token = uuid4().hex
    key = f"{_prefix()}:scan-lock:{normalized_id}"
    acquired = redis_client.set(key, _json({"instance_token": token}), ex=max(5, int(ttl_seconds)), nx=True)
    return token if acquired else None


def release_worker_scan_lock_sync(redis_client: Any, worker_id: str, *, lock_token: str) -> None:
    """Release a cross-process scan lock if still owned by this scan invocation."""
    normalized_id = worker_id.strip()
    if not normalized_id or not lock_token:
        return
    key = f"{_prefix()}:scan-lock:{normalized_id}"
    if hasattr(redis_client, "eval"):
        redis_client.eval(_RELEASE_IF_TOKEN_MATCHES_LUA, 1, key, lock_token)
    else:
        redis_client.delete(key)


class AndroidWorkerHeartbeatThread:
    """Background daemon heartbeat independent of Celery solo execution slots."""

    def __init__(
        self,
        *,
        worker_id: str,
        instance_token: str,
        instance_generation: int,
        queues: list[str] | None = None,
        interval_seconds: float | None = None,
        ttl_seconds: float | None = None,
        redis_client: Any | None = None,
        owns_client: bool | None = None,
        adb_ok_fn: Callable[[], bool] | None = None,
        busy_fn: Callable[[], bool] | None = None,
        on_conflict: Callable[[], None] | None = None,
    ) -> None:
        self.worker_id = normalize_worker_id(worker_id)
        self.instance_token = instance_token
        self.instance_generation = int(instance_generation)
        self.queues = queues or worker_queues_for(self.worker_id)
        self.interval_seconds = float(
            interval_seconds if interval_seconds is not None else max(5, int(settings.ANDROID_WORKER_HEARTBEAT_SECONDS))
        )
        self.ttl_seconds = float(
            ttl_seconds if ttl_seconds is not None else max(5, int(settings.ANDROID_WORKER_TTL_SECONDS))
        )
        self._owns_client = (redis_client is None) if owns_client is None else bool(owns_client)
        self._redis = redis_client
        self._adb_ok_fn = adb_ok_fn or (lambda: shutil.which("adb") is not None)
        self._busy_fn = busy_fn or (lambda: False)
        self._on_conflict = on_conflict
        self._stop_event = threading.Event()
        self._thread: threading.Thread | None = None
        self._initialized = False
        self.conflict_detected = False

    def _client(self) -> Any:
        if self._redis is None:
            self._redis = _sync_redis_client()
        return self._redis

    def beat_once(self) -> bool:
        try:
            adb_ok = bool(self._adb_ok_fn())
        except Exception:
            adb_ok = False
        try:
            busy = bool(self._busy_fn())
        except Exception:
            busy = False
        client = self._client()
        ttl = max(1, int(round(self.ttl_seconds)))
        ok = renew_android_worker_sync(
            client,
            self.worker_id,
            instance_generation=self.instance_generation,
            instance_token=self.instance_token,
            queues=self.queues,
            ttl_seconds=ttl,
            adb_ok=adb_ok,
            busy=busy,
        )
        if ok:
            self._initialized = True
            return True

        # Initial start without prior claim_android_worker_sync: try claiming current identity once.
        if not self._initialized:
            try:
                claim_android_worker_sync(
                    client,
                    self.worker_id,
                    instance_generation=self.instance_generation,
                    instance_token=self.instance_token,
                    queues=self.queues,
                    ttl_seconds=ttl,
                    adb_ok=adb_ok,
                    busy=busy,
                )
                self._initialized = True
                return True
            except AndroidWorkerConflictError:
                pass
        else:
            # Lease expired while running: only re-acquire with a NEW instance_generation if slot is empty.
            new_gen, new_token = generate_instance_identity()
            if new_gen <= self.instance_generation:
                new_gen = self.instance_generation + 1
            try:
                claim_android_worker_sync(
                    client,
                    self.worker_id,
                    instance_generation=new_gen,
                    instance_token=new_token,
                    queues=self.queues,
                    ttl_seconds=ttl,
                    adb_ok=adb_ok,
                    busy=busy,
                )
                self.instance_generation = new_gen
                self.instance_token = new_token
                if get_current_worker_id() == self.worker_id:
                    set_current_worker_runtime(self.worker_id, new_gen, new_token)
                logger.warning(
                    "Android Worker %s heartbeat expired; re-claimed with new generation %s",
                    self.worker_id,
                    new_gen,
                )
                return True
            except AndroidWorkerConflictError:
                pass

        self.conflict_detected = True
        if get_current_worker_id() == self.worker_id:
            mark_worker_runtime_conflict()
        self._stop_event.set()
        if self._on_conflict is not None:
            try:
                self._on_conflict()
            except Exception:
                logger.warning("Failed to run conflict callback for Android Worker %s", self.worker_id, exc_info=True)
        return False

    def _run(self) -> None:
        while not self._stop_event.wait(self.interval_seconds):
            try:
                self.beat_once()
            except Exception:
                logger.warning("Android Worker background heartbeat failed for %s", self.worker_id, exc_info=True)

    def start(self) -> None:
        if self._thread is not None and self._thread.is_alive():
            return
        self._stop_event.clear()
        self.beat_once()
        if self.conflict_detected:
            return
        self._thread = threading.Thread(
            target=self._run,
            name=f"android-worker-heartbeat-{self.worker_id}",
            daemon=True,
        )
        self._thread.start()

    def stop(self, *, release: bool = True) -> None:
        self._stop_event.set()
        if self._thread is not None:
            self._thread.join(timeout=2.0)
            self._thread = None
        if release and not self.conflict_detected and self._redis is not None:
            try:
                release_android_worker_sync(self._redis, self.worker_id, instance_token=self.instance_token)
            except Exception:
                logger.warning("Failed to release Android Worker lease for %s", self.worker_id, exc_info=True)
        if self._owns_client and self._redis is not None:
            close_fn = getattr(self._redis, "close", None)
            if callable(close_fn):
                try:
                    close_fn()
                except Exception:
                    pass
            self._redis = None


_RUNTIME_LOCK = threading.Lock()
_RUNTIME_WORKER_ID: str = ""
_RUNTIME_GENERATION: int | None = None
_RUNTIME_TOKEN: str = ""
_RUNTIME_ACTIVE_TASKS: int = 0
_RUNTIME_CONFLICT: bool = False


def set_current_worker_runtime(worker_id: str, generation: int, token: str) -> None:
    global _RUNTIME_WORKER_ID, _RUNTIME_GENERATION, _RUNTIME_TOKEN, _RUNTIME_CONFLICT
    with _RUNTIME_LOCK:
        _RUNTIME_WORKER_ID = worker_id
        _RUNTIME_GENERATION = int(generation)
        _RUNTIME_TOKEN = token
        _RUNTIME_CONFLICT = False


def clear_current_worker_runtime() -> None:
    global _RUNTIME_WORKER_ID, _RUNTIME_GENERATION, _RUNTIME_TOKEN, _RUNTIME_ACTIVE_TASKS, _RUNTIME_CONFLICT
    with _RUNTIME_LOCK:
        _RUNTIME_WORKER_ID = ""
        _RUNTIME_GENERATION = None
        _RUNTIME_TOKEN = ""
        _RUNTIME_ACTIVE_TASKS = 0
        _RUNTIME_CONFLICT = False


def mark_worker_runtime_conflict() -> None:
    global _RUNTIME_CONFLICT
    with _RUNTIME_LOCK:
        _RUNTIME_CONFLICT = True


def is_worker_runtime_conflicted() -> bool:
    with _RUNTIME_LOCK:
        return _RUNTIME_CONFLICT


def get_current_worker_id() -> str:
    with _RUNTIME_LOCK:
        return _RUNTIME_WORKER_ID


def get_current_worker_token() -> str:
    with _RUNTIME_LOCK:
        return _RUNTIME_TOKEN


def get_current_worker_generation() -> int | None:
    with _RUNTIME_LOCK:
        return _RUNTIME_GENERATION


def increment_active_tasks(delta: int) -> None:
    global _RUNTIME_ACTIVE_TASKS
    with _RUNTIME_LOCK:
        _RUNTIME_ACTIVE_TASKS = max(0, _RUNTIME_ACTIVE_TASKS + delta)


def is_slot_busy() -> bool:
    with _RUNTIME_LOCK:
        return _RUNTIME_ACTIVE_TASKS > 0


def verify_worker_execution_target(
    *,
    expected_worker_id: str | None = None,
    expected_generation: int | None = None,
) -> tuple[bool, str | None]:
    """Verify the executing worker matches the dispatched target worker and generation."""
    if is_worker_runtime_conflicted():
        return False, "worker_conflict_detected"
    active_worker_id = settings.ANDROID_WORKER_ID.strip() or get_current_worker_id()
    if expected_worker_id:
        if not active_worker_id or expected_worker_id.strip() != active_worker_id:
            return False, "worker_id_mismatch"
    if expected_generation is not None:
        current_gen = get_current_worker_generation()
        if current_gen is None:
            if settings.ANDROID_MULTI_NODE_ENABLED:
                return False, "worker_generation_mismatch"
        elif int(expected_generation) != int(current_gen):
            return False, "worker_generation_mismatch"
    return True, None
