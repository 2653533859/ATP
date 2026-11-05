"""管理员默认初始密码的持久化和权限回归。"""

from types import SimpleNamespace

import httpx
import pytest
from fastapi import FastAPI, HTTPException
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.api.v1 import users
from app.models.system_setting import SystemSetting


@pytest.mark.asyncio
async def test_default_password_is_encrypted_persistent_and_admin_only(tmp_path, monkeypatch):
    engine = create_async_engine(f"sqlite+aiosqlite:///{(tmp_path / 'settings.sqlite').as_posix()}")
    async with engine.begin() as connection:
        await connection.run_sync(SystemSetting.__table__.create)
    sessions = async_sessionmaker(engine, expire_on_commit=False)

    async def get_db():
        async with sessions() as session:
            yield session

    audit_details = []

    async def audit(_db, **kwargs):
        audit_details.append(kwargs)

    monkeypatch.setattr(users.settings, "DEFAULT_USER_INITIAL_PASSWORD", "old-default")
    monkeypatch.setattr(users, "require_server_workspace", lambda _action: None)
    monkeypatch.setattr(users, "write_audit_log", audit)
    app = FastAPI()
    app.include_router(users.router)
    app.dependency_overrides[users.get_db] = get_db
    app.dependency_overrides[users.require_admin] = lambda: SimpleNamespace(id=1, username="admin")

    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
        assert (await client.get("/users/initial-password")).json() == {"password": "old-default"}
        assert (await client.put("/users/initial-password", json={"password": "short"})).status_code == 422
        assert (await client.put("/users/initial-password", json={"password": "new-default"})).status_code == 200
        response = await client.get("/users/initial-password")
        assert response.json() == {"password": "new-default"}
        assert response.headers["cache-control"] == "no-store"
        async with sessions() as session:
            stored = await session.get(SystemSetting, "user_initial_password")
            assert stored and stored.value_encrypted != "new-default"
        assert "new-default" not in str(audit_details)

        def deny():
            raise HTTPException(status_code=403)

        app.dependency_overrides[users.require_admin] = deny
        assert (await client.put("/users/initial-password", json={"password": "other-default"})).status_code == 403
        assert (await client.get("/users/initial-password")).status_code == 403
        app.dependency_overrides[users.require_admin] = lambda: SimpleNamespace(id=1, username="admin")
        assert (await client.get("/users/initial-password")).json() == {"password": "new-default"}

    await engine.dispose()


async def _sqlite_sessions(tmp_path):
    engine = create_async_engine(f"sqlite+aiosqlite:///{(tmp_path / 'settings.sqlite').as_posix()}")
    async with engine.begin() as connection:
        await connection.run_sync(SystemSetting.__table__.create)
    return engine, async_sessionmaker(engine, expire_on_commit=False)


@pytest.mark.asyncio
async def test_initial_password_endpoints_require_server_workspace(tmp_path, monkeypatch):
    """本地模式不提供多用户能力，读取与写入默认初始密码都应统一返回 409。"""
    engine, sessions = await _sqlite_sessions(tmp_path)

    async def get_db():
        async with sessions() as session:
            yield session

    monkeypatch.setattr(users.settings, "ATP_LOCAL_MODE", True)
    app = FastAPI()
    app.include_router(users.router)
    app.dependency_overrides[users.get_db] = get_db
    app.dependency_overrides[users.require_admin] = lambda: SimpleNamespace(id=1, username="admin")

    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
        assert (await client.get("/users/initial-password")).status_code == 409
        assert (await client.put("/users/initial-password", json={"password": "new-default"})).status_code == 409

    await engine.dispose()


@pytest.mark.asyncio
async def test_initial_password_falls_back_when_ciphertext_is_unreadable(tmp_path, monkeypatch):
    """密钥轮换后历史密文解不开时，读取接口回退到内置默认值而不是 500。"""
    engine, sessions = await _sqlite_sessions(tmp_path)
    async with sessions() as session:
        session.add(SystemSetting(key="user_initial_password", value_encrypted="not-a-fernet-token"))
        await session.commit()

    async def get_db():
        async with sessions() as session:
            yield session

    monkeypatch.setattr(users.settings, "DEFAULT_USER_INITIAL_PASSWORD", "builtin-default")
    monkeypatch.setattr(users, "require_server_workspace", lambda _action: None)
    app = FastAPI()
    app.include_router(users.router)
    app.dependency_overrides[users.get_db] = get_db
    app.dependency_overrides[users.require_admin] = lambda: SimpleNamespace(id=1, username="admin")

    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/users/initial-password")
        assert response.status_code == 200
        assert response.json() == {"password": "builtin-default"}

    await engine.dispose()
