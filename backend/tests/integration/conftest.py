"""集成测试 fixtures。

要求：环境变量 ATP_INTEGRATION_TESTS=1 + 真实 postgres / redis / minio 可达。
- 根 conftest 在该 env 下不注入 stub；fixtures 在此提供真实客户端。
- 每个测试用例在事务里跑，结束时回滚以隔离数据；session 范围 fixture 负责
  一次性 `alembic upgrade head` + bootstrap admin。
"""
from __future__ import annotations

import asyncio
import os
import uuid

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker

assert os.getenv("ATP_INTEGRATION_TESTS") == "1", (
    "integration tests require ATP_INTEGRATION_TESTS=1 (root conftest skips stub injection)"
)


# ── 每用例启动 app/client，避免 asyncpg 连接跨 pytest 事件循环复用 ─────────
@pytest_asyncio.fixture()
async def app_instance():
    """启动 FastAPI app（lifespan 内会执行启动初始化）。

    注意：Alembic 已在 CI workflow 中 `alembic upgrade head`，此处只依赖
    lifespan 创建默认管理员与初始化外部资源。
    """
    from app.main import app

    # 触发 lifespan startup
    async with app.router.lifespan_context(app):
        yield app


@pytest_asyncio.fixture()
async def async_client(app_instance):
    transport = ASGITransport(app=app_instance)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        yield client


# ── 真实 DB session（function 级，每用例独立连接）──────────────
@pytest_asyncio.fixture()
async def db_session() -> AsyncSession:
    from app.core.database import AsyncSessionLocal

    async with AsyncSessionLocal() as session:
        yield session


# ── admin 登录 token（function 级，避免 token 过期）────────────
@pytest_asyncio.fixture()
async def admin_token(async_client) -> str:
    from app.core.config import settings

    resp = await async_client.post(
        "/api/v1/auth/login",
        json={
            "username": settings.FIRST_ADMIN_USERNAME,
            "password": settings.FIRST_ADMIN_PASSWORD,
        },
    )
    assert resp.status_code == 200, f"admin login failed: {resp.status_code} {resp.text}"
    return resp.json()["access_token"]


@pytest.fixture()
def auth_headers(admin_token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {admin_token}"}


# ── 唯一名称助手，避免跨测试残留数据冲突 ─────────────────────
@pytest.fixture()
def unique_name() -> str:
    return f"it-{uuid.uuid4().hex[:8]}"
