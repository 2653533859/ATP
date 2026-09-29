"""Redis-backed cooperative cancellation signals for Web case runs."""

from __future__ import annotations

import redis

from app.core.config import settings

_CANCEL_KEY_PREFIX = "atp:web-run:cancel:"
_CANCEL_TTL_SECONDS = 3600
_local_cancelled_runs: set[int] = set()


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
    if settings.ATP_LOCAL_MODE:
        _local_cancelled_runs.add(run_id)
        return
    client = create_control_client()
    try:
        client.set(f"{_CANCEL_KEY_PREFIX}{run_id}", "1", ex=_CANCEL_TTL_SECONDS)
    finally:
        client.close()


def is_cancel_requested(run_id: int, *, client: redis.Redis | None = None) -> bool:
    if settings.ATP_LOCAL_MODE:
        return run_id in _local_cancelled_runs
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
    if settings.ATP_LOCAL_MODE:
        _local_cancelled_runs.discard(run_id)
        return
    owned_client = client is None
    active_client = client or create_control_client()
    try:
        active_client.delete(f"{_CANCEL_KEY_PREFIX}{run_id}")
    except redis.RedisError:
        pass
    finally:
        if owned_client:
            active_client.close()
