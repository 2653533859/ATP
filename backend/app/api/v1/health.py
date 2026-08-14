"""运行时依赖健康检查。

The lightweight root ``/health`` endpoint remains public for process probes;
the dependency probe is an administrator-only diagnostic because it performs
live infrastructure calls and is intended for the startup configuration UI.
"""

import asyncio
import contextlib
from datetime import datetime, timezone
from time import perf_counter
from typing import Literal

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy import text

from app.api.deps import require_admin
from app.core.config import settings

router = APIRouter(prefix="/health", tags=["健康检查"])


class DependencyCheck(BaseModel):
    status: Literal["ok", "error"]
    latency_ms: float
    code: Literal["ok", "timeout", "unreachable", "bucket_missing"]


class DependencyHealthResponse(BaseModel):
    status: Literal["ok", "degraded"]
    checked_at: datetime
    dependencies: dict[str, DependencyCheck]


def _success(started: float) -> DependencyCheck:
    return DependencyCheck(status="ok", latency_ms=round((perf_counter() - started) * 1000, 1), code="ok")


def _failure(started: float, code: Literal["timeout", "unreachable", "bucket_missing"]) -> DependencyCheck:
    return DependencyCheck(status="error", latency_ms=round((perf_counter() - started) * 1000, 1), code=code)


async def _probe_postgres() -> DependencyCheck:
    started = perf_counter()
    try:
        # Keep these imports inside the probe: the unit-test suite intentionally
        # replaces shared infrastructure modules with lightweight stubs.
        from app.core.database import AsyncSessionLocal

        async with AsyncSessionLocal() as db:
            await asyncio.wait_for(
                db.execute(text("SELECT 1")),
                timeout=settings.POSTGRES_CONNECT_TIMEOUT_SECONDS,
            )
        return _success(started)
    except asyncio.TimeoutError:
        return _failure(started, "timeout")
    except Exception:
        return _failure(started, "unreachable")


async def _probe_redis() -> DependencyCheck:
    started = perf_counter()
    client = None
    try:
        from app.core.redis_client import close_async_redis, get_async_redis

        client = get_async_redis(db=2)
        await asyncio.wait_for(client.ping(), timeout=settings.REDIS_CONNECT_TIMEOUT_SECONDS)
        return _success(started)
    except asyncio.TimeoutError:
        return _failure(started, "timeout")
    except Exception:
        return _failure(started, "unreachable")
    finally:
        if client is not None:
            with contextlib.suppress(Exception):
                await close_async_redis(client)


async def _probe_minio() -> DependencyCheck:
    started = perf_counter()
    try:
        from app.core.minio_client import get_client

        bucket_exists = await asyncio.wait_for(
            asyncio.to_thread(get_client().bucket_exists, settings.MINIO_BUCKET),
            timeout=settings.MINIO_CONNECT_TIMEOUT_SECONDS,
        )
        return _success(started) if bucket_exists else _failure(started, "bucket_missing")
    except asyncio.TimeoutError:
        return _failure(started, "timeout")
    except Exception:
        return _failure(started, "unreachable")


@router.get("/dependencies", response_model=DependencyHealthResponse)
async def get_dependency_health(_admin=Depends(require_admin)) -> DependencyHealthResponse:
    postgres, redis, minio = await asyncio.gather(
        _probe_postgres(),
        _probe_redis(),
        _probe_minio(),
    )
    dependencies = {"postgres": postgres, "redis": redis, "minio": minio}
    return DependencyHealthResponse(
        status="ok" if all(item.status == "ok" for item in dependencies.values()) else "degraded",
        checked_at=datetime.now(timezone.utc),
        dependencies=dependencies,
    )
