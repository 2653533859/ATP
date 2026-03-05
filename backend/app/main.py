from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import select

from app.api.v1.router import router
from app.api.v1.ws import ws_router
from app.core.config import settings
from app.core.database import AsyncSessionLocal, engine
from app.core.security import hash_password
from app.models.base import Base
from app.models.user import User, UserRole  # noqa: F401
from app.models.project import Project, Module  # noqa: F401
from app.models.case import TestCase, TestRun, StepResult  # noqa: F401
from app.models.environment import Environment, EnvVariable  # noqa: F401
from app.models.device import Device  # noqa: F401


async def _init_admin():
    """首次启动时创建默认管理员"""
    async with AsyncSessionLocal() as db:
        result = await db.execute(select(User).where(User.username == settings.FIRST_ADMIN_USERNAME))
        if result.scalar_one_or_none() is None:
            admin = User(
                username=settings.FIRST_ADMIN_USERNAME,
                email=settings.FIRST_ADMIN_EMAIL,
                hashed_password=hash_password(settings.FIRST_ADMIN_PASSWORD),
                role=UserRole.admin,
            )
            db.add(admin)
            await db.commit()


@asynccontextmanager
async def lifespan(app: FastAPI):
    # 启动时兜底建表，避免首次部署无迁移文件时业务初始化直接失败。
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    # 启动时执行业务初始化
    await _init_admin()
    yield
    # 关闭时执行
    await engine.dispose()


app = FastAPI(
    title="ATP - 自动化测试平台",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(router)
app.include_router(ws_router)  # WebSocket 路由，路径以 /ws/ 开头


@app.get("/health")
async def health():
    return {"status": "ok"}
