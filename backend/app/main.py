from contextlib import asynccontextmanager
from pathlib import Path
from fastapi import FastAPI, Request
from fastapi import HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError

from app.api.v1.router import router
from app.api.v1.ws import ws_router
from app.api.v1.mock_server import router as mock_router
from app.core.config import settings
from app.core.database import AsyncSessionLocal, engine
from app.core.logging import setup_logging
from app.core.metrics import enable_metrics_for
from app.core.migrations_check import verify_alembic_head_or_warn
from app.core.minio_client import ensure_bucket
from app.core.otel import init_tracer, shutdown_tracer
from app.core.rate_limit import limiter
from app.middleware.csrf import CSRFMiddleware
from app.middleware.trace import TraceMiddleware
from app.core.security import hash_password
from app.models.bootstrap import load_all_models
from app.models.user import User, UserRole

load_all_models()


async def _init_admin():
    """首次启动时创建默认管理员，并对用户名/邮箱保持幂等。"""
    async with AsyncSessionLocal() as db:
        if settings.ATP_LOCAL_MODE and await db.scalar(select(func.count(User.id))):
            return
        admin_lookup = select(User).where(
            (User.username == settings.FIRST_ADMIN_USERNAME) | (User.email == settings.FIRST_ADMIN_EMAIL)
        )
        result = await db.execute(admin_lookup)
        if result.scalars().first() is None:
            admin = User(
                username=settings.FIRST_ADMIN_USERNAME,
                email=settings.FIRST_ADMIN_EMAIL,
                hashed_password=hash_password(settings.FIRST_ADMIN_PASSWORD),
                role=UserRole.admin,
            )
            db.add(admin)
            try:
                await db.commit()
            except IntegrityError:
                # Multiple API replicas can bootstrap concurrently. If another
                # replica won the insert, the existing identity is sufficient.
                await db.rollback()
                result = await db.execute(admin_lookup)
                if result.scalars().first() is None:
                    raise


@asynccontextmanager
async def lifespan(app: FastAPI):
    setup_logging()
    if settings.ATP_LOCAL_MODE:
        from app.core.database import sync_engine
        from app.core.local_schema import ensure_local_schema
        from app.core.local_run_ids import install_local_run_id_allocator

        ensure_local_schema(sync_engine)
        install_local_run_id_allocator()
    else:
        verify_alembic_head_or_warn()
    init_tracer(settings.OTEL_SERVICE_NAME)

    # 默认只通过 Alembic 管理表结构；仅在显式允许时才执行兜底建表。
    if settings.APP_AUTO_CREATE_TABLES:
        from app.models.base import Base

        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)

    # 启动时确保默认对象存储 bucket 可用，避免首次上传时才暴露配置问题。
    ensure_bucket()

    # 启动时执行业务初始化
    await _init_admin()
    if settings.ATP_LOCAL_MODE:
        from app.core.local_workspace import ensure_local_workspace
        from app.services.local_jobs import start_local_runner

        await ensure_local_workspace()
        start_local_runner()
    yield
    # 关闭时执行
    if settings.ATP_LOCAL_MODE:
        from app.services.local_jobs import stop_local_runner

        stop_local_runner()
    from app.api.v1.web_recordings import close_all_recordings

    await close_all_recordings()
    await engine.dispose()
    shutdown_tracer()


app = FastAPI(
    title="ATP - 自动化测试平台",
    version="1.0.0",
    lifespan=lifespan,
)

app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.add_middleware(CSRFMiddleware)
app.add_middleware(TraceMiddleware)

_LOCAL_UNSUPPORTED_WRITE_PREFIXES = (
    "/api/v1/suites",
    "/api/v1/plans",
    "/api/v1/device-mirror",
    "/api/v1/ios",
    "/api/v1/performance",
    "/api/v1/hermes",
    "/api/v1/ai-",
)


@app.middleware("http")
async def reject_unsupported_local_writes(request: Request, call_next):
    if (
        settings.ATP_LOCAL_MODE
        and request.method not in {"GET", "HEAD", "OPTIONS"}
        and request.url.path.startswith(_LOCAL_UNSUPPORTED_WRITE_PREFIXES)
    ):
        return JSONResponse(status_code=409, content={"detail": "此功能尚未纳入 Windows 本地模式首版"})
    return await call_next(request)


# Prometheus 指标必须在 include_router 之前，确保 instrumentator 覆盖所有 endpoint
enable_metrics_for(app)

app.include_router(router)
app.include_router(ws_router)  # WebSocket 路由，路径以 /ws/ 开头
app.include_router(mock_router)  # Mock 服务，路径以 /mock/ 开头

# 必须在路由注册后调用，以便自动埋 server span（包含路径模板）。
# OTEL endpoint 未配置时不挂载 OTel ASGI 中间件，保持本地/CI 的 no-op 行为。
if settings.OTEL_EXPORTER_OTLP_ENDPOINT:
    FastAPIInstrumentor.instrument_app(app)


@app.get("/health")
async def health():
    return {"status": "ok"}


if settings.ATP_LOCAL_MODE:
    _local_frontend_dist = Path(__file__).resolve().parents[2] / "frontend" / "dist"

    @app.get("/{path:path}", include_in_schema=False)
    async def local_frontend(path: str) -> FileResponse:
        if not _local_frontend_dist.is_dir() or path.startswith(("api/", "ws/", "mock/")):
            raise HTTPException(status_code=404)
        asset = (_local_frontend_dist / path).resolve()
        if not asset.is_relative_to(_local_frontend_dist.resolve()):
            raise HTTPException(status_code=404)
        if asset.is_file():
            return FileResponse(asset)
        if "." in Path(path).name:
            raise HTTPException(status_code=404)
        return FileResponse(_local_frontend_dist / "index.html")
