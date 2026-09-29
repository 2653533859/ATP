"""Cancellation signals for Android special runs in either runtime mode."""

from __future__ import annotations

import redis
from threading import Lock
from time import monotonic

from app.core.config import settings
from app.services.performance_control import create_control_client as create_redis_control_client

_CANCEL_KEY_PREFIX = "atp:mobile-special:cancel:"
_CANCEL_TTL_SECONDS = 3600
_local_cancelled: dict[str, float] = {}
_local_lock = Lock()


class _LocalControlClient:
    def set(self, key: str, _value: str, *, ex: int | None = None) -> None:
        with _local_lock:
            _local_cancelled[key] = monotonic() + (ex or _CANCEL_TTL_SECONDS)

    def get(self, key: str) -> str | None:
        with _local_lock:
            expires_at = _local_cancelled.get(key)
            if expires_at is None:
                return None
            if expires_at <= monotonic():
                del _local_cancelled[key]
                return None
            return "1"

    def delete(self, key: str) -> None:
        with _local_lock:
            _local_cancelled.pop(key, None)

    def close(self) -> None:
        pass


def create_control_client() -> redis.Redis | _LocalControlClient:
    return _LocalControlClient() if settings.ATP_LOCAL_MODE else create_redis_control_client()


def request_cancel(run_id: int) -> None:
    client = create_control_client()
    try:
        client.set(f"{_CANCEL_KEY_PREFIX}{run_id}", "1", ex=_CANCEL_TTL_SECONDS)
    finally:
        client.close()


def is_cancel_requested(run_id: int, *, client: redis.Redis | _LocalControlClient | None = None) -> bool:
    owned_client = client is None
    active_client = client or create_control_client()
    try:
        return bool(active_client.get(f"{_CANCEL_KEY_PREFIX}{run_id}"))
    except redis.RedisError:
        return False
    finally:
        if owned_client:
            active_client.close()


def clear_cancel_request(run_id: int, *, client: redis.Redis | _LocalControlClient | None = None) -> None:
    owned_client = client is None
    active_client = client or create_control_client()
    try:
        active_client.delete(f"{_CANCEL_KEY_PREFIX}{run_id}")
    except redis.RedisError:
        pass
    finally:
        if owned_client:
            active_client.close()
