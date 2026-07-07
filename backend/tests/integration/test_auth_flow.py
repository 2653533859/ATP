"""集成路径 1：登录 → 拿 token → 用 token 访问受保护资源。"""

import pytest


@pytest.mark.integration
@pytest.mark.asyncio
async def test_login_returns_access_and_refresh_token(async_client):
    from app.core.config import settings

    resp = await async_client.post(
        "/api/v1/auth/login",
        json={
            "username": settings.FIRST_ADMIN_USERNAME,
            "password": settings.FIRST_ADMIN_PASSWORD,
        },
    )
    assert resp.status_code == 200, resp.text
    payload = resp.json()
    assert payload["access_token"]
    assert payload["refresh_token"]
    assert payload.get("token_type", "bearer").lower() == "bearer"


@pytest.mark.integration
@pytest.mark.asyncio
async def test_login_wrong_password_returns_401(async_client):
    from app.core.config import settings

    resp = await async_client.post(
        "/api/v1/auth/login",
        json={
            "username": settings.FIRST_ADMIN_USERNAME,
            "password": "definitely-wrong-password",
        },
    )
    assert resp.status_code == 401


@pytest.mark.integration
@pytest.mark.asyncio
async def test_token_allows_access_to_me(async_client, auth_headers):
    resp = await async_client.get("/api/v1/auth/me", headers=auth_headers)
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["username"]
    assert body.get("is_active") is True


@pytest.mark.integration
@pytest.mark.asyncio
async def test_missing_token_blocks_protected_route(async_client):
    resp = await async_client.get("/api/v1/auth/me")
    assert resp.status_code in (401, 403)
