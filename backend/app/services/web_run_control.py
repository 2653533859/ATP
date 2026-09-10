"""Redis-backed cooperative cancellation signals for Web case runs."""

from __future__ import annotations

import redis

from app.core.config import settings

_CANCEL_KEY_PREFIX = "atp:web-run:cancel:"
_CANCEL_TTL_SECONDS = 3600


def _redis_url(db: int = 2) -> str:
    return settings.redis_url(db)


def create_control_client() -> redis.Redis:
    timeout = settings.REDIS_CONNECT_TIMEOUT_SECONDS
    return redis.Redis.from_url(
        _redis_url(),
        decode_responses=True,
        socket_connect_timeout=timeout,
        socket_timeout=timeout,
    )


def request_cancel(run_id: int) -> None:
    client = create_control_client()
    try:
        client.set(f"{_CANCEL_KEY_PREFIX}{run_id}", "1", ex=_CANCEL_TTL_SECONDS)
    finally:
        client.close()


def is_cancel_requested(run_id: int, *, client: redis.Redis | None = None) -> bool:
    owned_client = client is None
    active_client = client or create_control_client()
    try:
        return bool(active_client.get(f"{_CANCEL_KEY_PREFIX}{run_id}"))
    except redis.RedisError:
        return False
    finally:
        if owned_client:
            active_client.close()


def clear_cancel_request(run_id: int, *, client: redis.Redis | None = None) -> None:
    owned_client = client is None
    active_client = client or create_control_client()
    try:
        active_client.delete(f"{_CANCEL_KEY_PREFIX}{run_id}")
    except redis.RedisError:
        pass
    finally:
        if owned_client:
            active_client.close()
