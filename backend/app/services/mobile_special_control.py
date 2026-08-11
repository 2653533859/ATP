"""Redis-backed cancellation signals for Android special runs."""

from __future__ import annotations

import redis

from app.services.performance_control import create_control_client

_CANCEL_KEY_PREFIX = "atp:mobile-special:cancel:"
_CANCEL_TTL_SECONDS = 3600


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
