"""HTTP/GraphQL 执行器共享的高级认证辅助逻辑。"""

from __future__ import annotations

from collections.abc import Callable
import math
import time
from typing import Any

import httpx


def build_digest_auth(auth_config: dict[str, Any], render: Callable[[str], str]) -> httpx.DigestAuth:
    username = render(str(auth_config.get("username", "")))
    password = render(str(auth_config.get("password", "")))
    if not username:
        raise ValueError("Digest 认证缺少用户名")
    return httpx.DigestAuth(username, password)


async def resolve_oauth2_client_credentials_token(
    auth_config: dict[str, Any],
    render: Callable[[str], str],
    timeout: float,
    cache: dict[str, tuple[str, float]],
) -> str:
    """获取并缓存 client_credentials token；不会把 token 返回到执行证据。"""

    token_url = render(str(auth_config.get("token_url", ""))).strip()
    client_id = render(str(auth_config.get("client_id", "")))
    client_secret = render(str(auth_config.get("client_secret", "")))
    if not token_url or not client_id or not client_secret:
        raise ValueError("OAuth2 Client Credentials 缺少 token URL、Client ID 或 Client Secret")

    scope = render(str(auth_config.get("scope", ""))).strip()
    audience = render(str(auth_config.get("audience", ""))).strip()
    auth_method = str(auth_config.get("token_endpoint_auth_method", "client_secret_basic"))
    if auth_method not in {"client_secret_basic", "client_secret_post"}:
        raise ValueError("OAuth2 token endpoint 认证方式不受支持")
    cache_key = "|".join((token_url, client_id, scope, audience, auth_method))
    cached = cache.get(cache_key)
    if cached and time.monotonic() < cached[1]:
        return cached[0]

    form_data: dict[str, str] = {"grant_type": "client_credentials"}
    if scope:
        form_data["scope"] = scope
    if audience:
        form_data["audience"] = audience
    request_kwargs: dict[str, Any] = {"data": form_data}
    if auth_method == "client_secret_post":
        form_data["client_id"] = client_id
        form_data["client_secret"] = client_secret
    else:
        request_kwargs["auth"] = (client_id, client_secret)

    async with httpx.AsyncClient(timeout=timeout) as client:
        response = await client.post(token_url, **request_kwargs)
    if response.status_code < 200 or response.status_code >= 300:
        raise ValueError(f"OAuth2 token 请求失败（HTTP {response.status_code}）")
    try:
        payload = response.json()
    except ValueError as exc:
        raise ValueError("OAuth2 token 响应不是合法 JSON") from exc
    if not isinstance(payload, dict) or not payload.get("access_token"):
        raise ValueError("OAuth2 token 响应缺少 access_token")

    token_type = str(payload.get("token_type") or "Bearer")
    token = f"{token_type} {payload['access_token']}"
    try:
        expires_in = float(payload.get("expires_in", 300))
    except (TypeError, ValueError):
        expires_in = 300
    if not math.isfinite(expires_in) or expires_in <= 0:
        expires_in = 300
    refresh_margin = min(30.0, expires_in * 0.1)
    cache[cache_key] = (token, time.monotonic() + max(0.0, expires_in - refresh_margin))
    return token
