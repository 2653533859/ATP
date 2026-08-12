import asyncio

import httpx
import pytest

from app.services import api_auth


def test_build_digest_auth_renders_credentials():
    auth = api_auth.build_digest_auth(
        {"username": "{{user}}", "password": "{{password}}"},
        lambda value: value.replace("{{user}}", "alice").replace("{{password}}", "secret"),
    )

    assert isinstance(auth, httpx.DigestAuth)


def test_build_digest_auth_requires_username():
    with pytest.raises(ValueError, match="用户名"):
        api_auth.build_digest_auth({"username": "", "password": "p"}, lambda value: value)


def test_oauth2_client_credentials_uses_basic_and_caches(monkeypatch):
    calls = []

    class _Response:
        status_code = 200

        def json(self):
            return {"access_token": "token-1", "token_type": "Bearer"}

    class _Client:
        def __init__(self, *args, **kwargs):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            return None

        async def post(self, url, **kwargs):
            calls.append((url, kwargs))
            return _Response()

    monkeypatch.setattr(api_auth.httpx, "AsyncClient", _Client)
    config = {
        "token_url": "https://issuer.test/token",
        "client_id": "client-1",
        "client_secret": "secret-1",
        "scope": "read",
    }
    cache = {}
    token_one = asyncio.run(api_auth.resolve_oauth2_client_credentials_token(config, lambda value: value, 5, cache))
    token_two = asyncio.run(api_auth.resolve_oauth2_client_credentials_token(config, lambda value: value, 5, cache))

    assert token_one == token_two == "Bearer token-1"
    assert len(calls) == 1
    assert calls[0][1]["auth"] == ("client-1", "secret-1")
    assert calls[0][1]["data"] == {"grant_type": "client_credentials", "scope": "read"}


def test_oauth2_client_credentials_supports_client_secret_post(monkeypatch):
    captured = {}

    class _Response:
        status_code = 200

        def json(self):
            return {"access_token": "token-2"}

    class _Client:
        def __init__(self, *args, **kwargs):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            return None

        async def post(self, url, **kwargs):
            captured.update(kwargs)
            return _Response()

    monkeypatch.setattr(api_auth.httpx, "AsyncClient", _Client)
    asyncio.run(
        api_auth.resolve_oauth2_client_credentials_token(
            {
                "token_url": "https://issuer.test/token",
                "client_id": "client-1",
                "client_secret": "secret-1",
                "token_endpoint_auth_method": "client_secret_post",
                "audience": "api",
            },
            lambda value: value,
            5,
            {},
        )
    )

    assert "auth" not in captured
    assert captured["data"] == {
        "grant_type": "client_credentials",
        "client_id": "client-1",
        "client_secret": "secret-1",
        "audience": "api",
    }


def test_oauth2_client_credentials_refreshes_after_expiry(monkeypatch):
    calls = []
    now = [100.0]

    class _Response:
        status_code = 200

        def json(self):
            return {"access_token": f"token-{len(calls)}", "expires_in": 10}

    class _Client:
        def __init__(self, *args, **kwargs):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            return None

        async def post(self, url, **kwargs):
            calls.append((url, kwargs))
            return _Response()

    monkeypatch.setattr(api_auth.httpx, "AsyncClient", _Client)
    monkeypatch.setattr(api_auth.time, "monotonic", lambda: now[0])
    config = {
        "token_url": "https://issuer.test/token",
        "client_id": "client-1",
        "client_secret": "secret-1",
    }
    cache = {}

    first = asyncio.run(api_auth.resolve_oauth2_client_credentials_token(config, lambda value: value, 5, cache))
    now[0] = 105.0
    second = asyncio.run(api_auth.resolve_oauth2_client_credentials_token(config, lambda value: value, 5, cache))
    now[0] = 110.0
    third = asyncio.run(api_auth.resolve_oauth2_client_credentials_token(config, lambda value: value, 5, cache))

    assert first == second == "Bearer token-1"
    assert third == "Bearer token-2"
    assert len(calls) == 2


def test_oauth2_client_credentials_rejects_unknown_token_endpoint_auth_method():
    with pytest.raises(ValueError, match="认证方式"):
        asyncio.run(
            api_auth.resolve_oauth2_client_credentials_token(
                {
                    "token_url": "https://issuer.test/token",
                    "client_id": "client-1",
                    "client_secret": "secret-1",
                    "token_endpoint_auth_method": "unknown",
                },
                lambda value: value,
                5,
                {},
            )
        )
