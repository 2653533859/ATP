"""
Redis 客户端封装

- publish_run_event：异步发布（供执行器在 asyncio 上下文中调用）
- get_async_redis：异步 Redis 连接（供 FastAPI WebSocket subscribe）
"""
import json
import redis.asyncio as aioredis
from app.core.config import settings


def _redis_url(db: int = 2) -> str:
    auth = f":{settings.REDIS_PASSWORD}@" if settings.REDIS_PASSWORD else ""
    return f"redis://{auth}{settings.REDIS_HOST}:{settings.REDIS_PORT}/{db}"


def get_async_redis() -> aioredis.Redis:
    """返回一个新的异步 Redis 连接（调用方负责关闭）"""
    return aioredis.from_url(_redis_url(), decode_responses=True)


async def publish_run_event(run_id: int, payload: dict) -> None:
    """发布执行事件到 Redis channel `atp:run:{run_id}`"""
    r = get_async_redis()
    try:
        await r.publish(f"atp:run:{run_id}", json.dumps(payload, ensure_ascii=False))
    finally:
        await r.aclose()
