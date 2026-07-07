"""ATP Mock Server 独立 FastAPI 子应用（P1.3）。

设计目标：
- 仅挂载 mock 路由，对外提供不带 /mock 前缀的 URL（例如 http://host:18000/{project_id}/{path}）
- 共用主应用的数据库 / Redis / MinIO 配置；规则变更通过 Redis 缓存失效跨进程同步
- 不接入 auth / CORS / rate_limit / CSRF：Mock 服务通常对内开放，按部署侧网络隔离

启动方式：
    uvicorn app.mock_main:app --host 0.0.0.0 --port ${MOCK_STANDALONE_PORT:-18000}

部署形态见 docs/mock-standalone.md。
"""

from contextlib import asynccontextmanager

from fastapi import FastAPI, Request

from app.api.v1.mock_server import mock_endpoint
from app.core.config import settings
from app.core.logging import setup_logging
from app.core.otel import init_tracer, shutdown_tracer
from app.models.bootstrap import load_all_models

load_all_models()


@asynccontextmanager
async def lifespan(_app: FastAPI):
    setup_logging()
    init_tracer(f"{settings.OTEL_SERVICE_NAME}-mock")
    # 懒导入 ensure_bucket / engine：避免 import 时强耦合底层（便于无 DB/MinIO 环境的 import 校验）
    try:
        from app.core.minio_client import ensure_bucket

        ensure_bucket()
    except Exception:
        pass
    yield
    try:
        from app.core.database import engine

        await engine.dispose()
    except Exception:
        pass
    shutdown_tracer()


app = FastAPI(
    title="ATP Mock Server",
    version="1.0.0",
    lifespan=lifespan,
)


@app.get("/health")
async def health():
    return {"status": "ok", "service": "mock-standalone"}


# 复用主应用的 mock_endpoint 实现，但暴露为裸路径（无 /mock 前缀）。
app.api_route(
    "/{project_id}/{path:path}",
    methods=["GET", "POST", "PUT", "DELETE", "PATCH", "HEAD", "OPTIONS"],
    name="mock_endpoint_standalone",
)(mock_endpoint)
