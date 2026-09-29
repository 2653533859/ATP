"""Isolation contract for the single-user Windows profile."""

from __future__ import annotations

import pytest

from app.core.config import Settings, get_settings


def test_local_settings_ignore_server_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ATP_LOCAL_MODE", "true")
    monkeypatch.setenv("APP_ENV", "local")
    monkeypatch.setenv("APP_SECRET_KEY", "local-private-test-secret")
    monkeypatch.setenv("FIRST_ADMIN_PASSWORD", "local-private-test-password")
    monkeypatch.setenv("POSTGRES_HOST", "server.example")
    monkeypatch.setenv("REDIS_HOST", "server.example")
    monkeypatch.setenv("MINIO_HOST", "server.example")
    monkeypatch.setenv("ATP_LOCAL_PRIVATE_POSTGRES_HOST", "hidden-server.example")

    configured = get_settings.__wrapped__()

    assert configured.ATP_LOCAL_MODE is True
    assert configured.POSTGRES_HOST == "localhost"
    assert configured.REDIS_HOST == "localhost"
    assert configured.MINIO_HOST == "localhost"
    assert configured.DATABASE_URL.startswith("sqlite+aiosqlite:///")
    assert configured.ACCESS_COOKIE_NAME == "atp_local_access_token"
    assert configured.REFRESH_COOKIE_NAME == "atp_local_refresh_token"


def test_local_settings_require_private_secrets(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ATP_LOCAL_MODE", "true")
    monkeypatch.setenv("APP_ENV", "local")
    monkeypatch.delenv("APP_SECRET_KEY", raising=False)
    monkeypatch.delenv("FIRST_ADMIN_PASSWORD", raising=False)

    with pytest.raises(ValueError, match="local profile requires"):
        get_settings.__wrapped__()


def test_server_cookie_names_remain_compatible() -> None:
    configured = Settings(_env_file=None, ATP_LOCAL_MODE=False)

    assert configured.ACCESS_COOKIE_NAME == "atp_access_token"
    assert configured.REFRESH_COOKIE_NAME == "atp_refresh_token"
