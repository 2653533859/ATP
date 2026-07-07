from collections.abc import AsyncGenerator

from sqlalchemy import create_engine, event
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from sqlalchemy.orm import sessionmaker
from app.core.config import settings
from app.core.slow_query import make_after_cursor_handler, on_before_cursor_execute

engine = create_async_engine(
    settings.DATABASE_URL,
    echo=settings.APP_ENV == "development",
    pool_pre_ping=True,
)

AsyncSessionLocal = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


# 同步 engine + session（供 Celery 任务使用）
_sync_url = settings.DATABASE_URL.replace("+asyncpg", "+psycopg2")
sync_engine = create_engine(
    _sync_url,
    echo=settings.APP_ENV == "development",
    pool_pre_ping=True,
)
sync_session_factory = sessionmaker(bind=sync_engine, expire_on_commit=False)


def _attach_slow_query_listeners() -> None:
    if not settings.SLOW_QUERY_LOG_ENABLED:
        return
    after_handler = make_after_cursor_handler(settings.SLOW_QUERY_THRESHOLD_MS)
    for eng in (sync_engine, engine.sync_engine):
        event.listen(eng, "before_cursor_execute", on_before_cursor_execute)
        event.listen(eng, "after_cursor_execute", after_handler)


_attach_slow_query_listeners()


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    async with AsyncSessionLocal() as session:
        yield session
