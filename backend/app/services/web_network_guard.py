"""Playwright browser request guard used by Web execution and recording."""

from __future__ import annotations

import asyncio
import re
from typing import Any
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from app.core.url_security import validate_public_http_url


_SENSITIVE_URL_PARAM_RE = re.compile(
    r"(?:token|secret|password|passwd|api[_-]?key|authorization|cookie|signature|sig|credential)",
    re.IGNORECASE,
)
_NO_NETWORK_SCHEMES = {"about", "blob", "data"}
_BROWSER_NETWORK_SCHEMES = {"http", "https", "ws", "wss"}


def sanitize_network_url(url: str) -> str:
    """Remove fragments and redact credentials/sensitive query values from evidence."""
    try:
        parsed = urlsplit(url)
        query = urlencode(
            [
                (key, "***" if _SENSITIVE_URL_PARAM_RE.search(key) else value)
                for key, value in parse_qsl(parsed.query, keep_blank_values=True)
            ]
        )
        netloc = parsed.netloc
        if "@" in netloc:
            userinfo, host = netloc.rsplit("@", 1)
            username = userinfo.split(":", 1)[0]
            netloc = f"{username}:***@{host}"
        return urlunsplit((parsed.scheme, netloc, parsed.path, query, ""))
    except ValueError:
        return "[invalid-url]"


def validate_browser_request_url(value: str) -> str:
    """Validate one URL observed by Playwright before allowing network access.

    Playwright also reports browser-local ``about:``, ``blob:`` and ``data:``
    URLs. They do not create an outbound connection and are therefore allowed.
    WebSocket URLs use the same host policy as HTTP URLs.
    """
    normalized = value.strip()
    parsed = urlsplit(normalized)
    scheme = parsed.scheme.lower()
    if scheme in _NO_NETWORK_SCHEMES:
        return normalized
    if scheme not in _BROWSER_NETWORK_SCHEMES or not parsed.hostname:
        raise ValueError("浏览器请求协议不被允许")
    if scheme in {"ws", "wss"}:
        http_scheme = "https" if scheme == "wss" else "http"
        normalized_for_http = urlunsplit((http_scheme, parsed.netloc, parsed.path, parsed.query, ""))
        validate_public_http_url(normalized_for_http)
        return normalized
    return validate_public_http_url(normalized)


async def guard_browser_request(
    route: Any,
    blocked_requests: list[dict[str, Any]],
    *,
    max_blocked_requests: int = 100,
) -> bool:
    """Validate and continue a Playwright route, aborting unsafe requests."""
    request = route.request
    url = str(request.url)
    try:
        await asyncio.to_thread(validate_browser_request_url, url)
    except Exception as exc:
        if len(blocked_requests) < max_blocked_requests:
            blocked_requests.append(
                {
                    "url": sanitize_network_url(url),
                    "resource_type": str(getattr(request, "resource_type", "unknown")),
                    "reason": str(exc).strip()[:500] or type(exc).__name__,
                }
            )
        await route.abort("blockedbyclient")
        return False
    await route.continue_()
    return True
