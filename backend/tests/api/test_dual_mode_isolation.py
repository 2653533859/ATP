"""Tests for N3.4 Dual-Mode Switching, Authentication Isolation, and Backend Protection.

Verifies:
1. Cookie name and path isolation between local mode and server mode.
2. Logout in one mode does not delete cookies of the other mode.
3. WebSocket token extraction matches the active mode's cookie name.
4. Middleware enforces X-ATP-Client-Mode matching and rejects mismatched requests with 409.
5. Local configuration barriers protect against connecting to server infrastructure.
"""

from __future__ import annotations

import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock

from starlette.requests import Request
from starlette.responses import JSONResponse, Response
from app.api.v1 import auth as auth_module
from app.api.v1 import ws as ws_module
from app.core.config import settings
from app.main import reject_unsupported_local_writes


def test_auth_cookie_isolation_local_mode(monkeypatch):
    """Local mode must use atp_local_* cookie names and only clear local cookies on logout."""
    monkeypatch.setattr(settings, "ATP_LOCAL_MODE", True)

    assert settings.ACCESS_COOKIE_NAME == "atp_local_access_token"
    assert settings.REFRESH_COOKIE_NAME == "atp_local_refresh_token"

    res = Response()
    auth_module._set_auth_cookies(res, "local_access_token_val", "local_refresh_token_val")

    # Inspect set-cookie headers
    cookie_headers = [v for k, v in res.raw_headers if k.lower() == b"set-cookie"]
    cookie_texts = [c.decode("latin1") for c in cookie_headers]

    assert any(c.startswith("atp_local_access_token=") for c in cookie_texts)
    assert any(c.startswith("atp_local_refresh_token=") for c in cookie_texts)
    assert not any(c.startswith("atp_access_token=") for c in cookie_texts)
    assert not any(c.startswith("atp_refresh_token=") for c in cookie_texts)

    # Logout must delete local cookies without touching server cookies
    logout_res = Response()
    auth_module._clear_auth_cookies(logout_res)
    logout_headers = [v.decode("latin1") for k, v in logout_res.raw_headers if k.lower() == b"set-cookie"]

    assert any("atp_local_access_token=" in c and "max-age=0" in c.lower() for c in logout_headers)
    assert any("atp_local_refresh_token=" in c and "max-age=0" in c.lower() for c in logout_headers)
    assert not any("atp_access_token=" in c and "atp_local" not in c for c in logout_headers)


def test_auth_cookie_isolation_server_mode(monkeypatch):
    """Server mode must use atp_* cookie names and only clear server cookies on logout."""
    monkeypatch.setattr(settings, "ATP_LOCAL_MODE", False)

    assert settings.ACCESS_COOKIE_NAME == "atp_access_token"
    assert settings.REFRESH_COOKIE_NAME == "atp_refresh_token"

    res = Response()
    auth_module._set_auth_cookies(res, "server_access_token_val", "server_refresh_token_val")

    cookie_headers = [v for k, v in res.raw_headers if k.lower() == b"set-cookie"]
    cookie_texts = [c.decode("latin1") for c in cookie_headers]

    assert any(c.startswith("atp_access_token=") for c in cookie_texts)
    assert any(c.startswith("atp_refresh_token=") for c in cookie_texts)
    assert not any(c.startswith("atp_local_access_token=") for c in cookie_texts)
    assert not any(c.startswith("atp_local_refresh_token=") for c in cookie_texts)

    # Logout in server mode must delete server cookies only
    logout_res = Response()
    auth_module._clear_auth_cookies(logout_res)
    logout_headers = [v.decode("latin1") for k, v in logout_res.raw_headers if k.lower() == b"set-cookie"]

    assert any("atp_access_token=" in c and "max-age=0" in c.lower() and "atp_local" not in c for c in logout_headers)
    assert any("atp_refresh_token=" in c and "max-age=0" in c.lower() and "atp_local" not in c for c in logout_headers)
    assert not any("atp_local_access_token=" in c for c in logout_headers)


def test_ws_cookie_isolation(monkeypatch):
    """WebSocket authentication only reads the active mode's cookie."""
    # 1. Local mode: only atp_local_access_token is inspected
    monkeypatch.setattr(settings, "ATP_LOCAL_MODE", True)

    server_cookie_only_ws = SimpleNamespace(
        cookies={"atp_access_token": "some_token"},
        query_params={},
    )
    # _get_ws_user checks settings.ACCESS_COOKIE_NAME
    # If the token is not found, it returns None
    result = asyncio.run(ws_module._get_ws_user(server_cookie_only_ws))
    assert result is None

    # 2. Server mode: only atp_access_token is inspected
    monkeypatch.setattr(settings, "ATP_LOCAL_MODE", False)

    local_cookie_only_ws = SimpleNamespace(
        cookies={"atp_local_access_token": "some_token"},
        query_params={},
    )
    result = asyncio.run(ws_module._get_ws_user(local_cookie_only_ws))
    assert result is None


def test_client_mode_mismatch_middleware_guard(monkeypatch):
    """Middleware rejects mismatched X-ATP-Client-Mode header with 409."""
    # Scenario A: Backend is local, client declares server mode -> 409
    monkeypatch.setattr(settings, "ATP_LOCAL_MODE", True)

    request_server_on_local = Request(
        {
            "type": "http",
            "method": "POST",
            "path": "/api/v1/projects",
            "headers": [(b"x-atp-client-mode", b"server")],
        }
    )

    call_next = AsyncMock(return_value=JSONResponse({"status": "ok"}))
    response = asyncio.run(reject_unsupported_local_writes(request_server_on_local, call_next))

    assert response.status_code == 409
    assert b"\xe4\xb8\x8d\xe4\xb8\x80\xe8\x87\xb4" in response.body  # "不一致"
    call_next.assert_not_called()

    # Scenario B: Backend is local, client declares local mode -> passes through
    request_local_on_local = Request(
        {
            "type": "http",
            "method": "GET",
            "path": "/api/v1/projects",
            "headers": [(b"x-atp-client-mode", b"local")],
        }
    )
    call_next = AsyncMock(return_value=JSONResponse({"status": "ok"}))
    response = asyncio.run(reject_unsupported_local_writes(request_local_on_local, call_next))
    assert response.status_code == 200
    call_next.assert_called_once()

    # Scenario C: Backend is server, client declares local mode -> 409
    monkeypatch.setattr(settings, "ATP_LOCAL_MODE", False)

    request_local_on_server = Request(
        {
            "type": "http",
            "method": "POST",
            "path": "/api/v1/projects",
            "headers": [(b"x-atp-client-mode", b"local")],
        }
    )
    call_next = AsyncMock(return_value=JSONResponse({"status": "ok"}))
    response = asyncio.run(reject_unsupported_local_writes(request_local_on_server, call_next))
    assert response.status_code == 409
    assert b"\xe4\xb8\x8d\xe4\xb8\x80\xe8\x87\xb4" in response.body
    call_next.assert_not_called()

    # Scenario D: /api/v1/runtime is exempted so mode probing always works
    request_probe = Request(
        {
            "type": "http",
            "method": "GET",
            "path": "/api/v1/runtime",
            "headers": [(b"x-atp-client-mode", b"local")],
        }
    )
    call_next = AsyncMock(return_value=JSONResponse({"status": "ok"}))
    response = asyncio.run(reject_unsupported_local_writes(request_probe, call_next))
    assert response.status_code == 200
    call_next.assert_called_once()


def test_local_configuration_protection(monkeypatch):
    """Local configuration never connects to server infrastructure."""
    monkeypatch.setattr(settings, "ATP_LOCAL_MODE", True)

    assert settings.DATABASE_URL.startswith("sqlite+aiosqlite:///")
    assert settings.SYNC_DATABASE_URL.startswith("sqlite+pysqlite:///")
    assert settings.CELERY_BROKER_URL == "memory://"
    assert settings.CELERY_RESULT_BACKEND == "cache+memory://"

    import pytest

    with pytest.raises(RuntimeError, match="Redis is unavailable in Windows local mode"):
        settings.redis_url(0)
