"""Encrypted project-scoped cookie sessions for API case execution."""

from __future__ import annotations

import json
from http.cookiejar import Cookie
from typing import Any

from cryptography.fernet import InvalidToken
import httpx

from app.core.encryption import decrypt, encrypt
from app.core import redis_client as _redis_client

get_async_redis = _redis_client.get_async_redis


async def close_async_redis(redis: Any) -> None:
    """Close Redis across production clients and lightweight test doubles."""
    close = getattr(_redis_client, "close_async_redis", None)
    if close is not None:
        await close(redis)
        return
    close_method = getattr(redis, "aclose", None)
    if close_method is not None:
        await close_method()


API_SESSION_TTL_SECONDS = 8 * 60 * 60


def _session_key(project_id: int) -> str:
    return f"atp:api-session:project:{project_id}"


def serialize_cookies(cookies: httpx.Cookies) -> list[dict[str, Any]]:
    """Convert an httpx cookie jar to a JSON-safe representation."""
    return [
        {
            "name": cookie.name,
            "value": cookie.value,
            "domain": cookie.domain,
            "path": cookie.path,
            "expires": cookie.expires,
            "secure": cookie.secure,
        }
        for cookie in cookies.jar
    ]


def apply_cookies(cookies: httpx.Cookies, serialized: list[dict[str, Any]]) -> None:
    """Load serialized cookies into an httpx cookie jar."""
    for item in serialized:
        name = str(item.get("name") or "").strip()
        if not name:
            continue
        domain = str(item.get("domain") or "")
        path = str(item.get("path") or "/") or "/"
        try:
            expires = None if item.get("expires") is None else int(item["expires"])
        except (TypeError, ValueError):
            expires = None
        cookies.jar.set_cookie(
            Cookie(
                version=0,
                name=name,
                value=str(item.get("value") or ""),
                port=None,
                port_specified=False,
                domain=domain,
                domain_specified=bool(domain),
                domain_initial_dot=domain.startswith("."),
                path=path,
                path_specified=True,
                secure=bool(item.get("secure", False)),
                expires=expires,
                discard=expires is None,
                comment=None,
                comment_url=None,
                rest={},
                rfc2109=False,
            )
        )


async def load_project_api_session(project_id: int) -> list[dict[str, Any]]:
    """Load a project cookie session; unreadable data degrades to empty."""
    redis = get_async_redis()
    try:
        encrypted = await redis.get(_session_key(project_id))
        if not encrypted:
            return []
        try:
            value = json.loads(decrypt(encrypted))
        except (InvalidToken, TypeError, ValueError, json.JSONDecodeError):
            return []
        return value if isinstance(value, list) else []
    finally:
        await close_async_redis(redis)


async def save_project_api_session(project_id: int, cookies: list[dict[str, Any]]) -> None:
    """Persist a project cookie session encrypted in Redis with a bounded TTL."""
    redis = get_async_redis()
    try:
        payload = encrypt(json.dumps(cookies, ensure_ascii=False))
        await redis.set(_session_key(project_id), payload, ex=API_SESSION_TTL_SECONDS)
    finally:
        await close_async_redis(redis)
