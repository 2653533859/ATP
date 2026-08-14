"""
Redis 客户端封装

- publish_run_event：异步发布（供执行器在 asyncio 上下文中调用）
- get_async_redis：异步 Redis 连接（供 FastAPI WebSocket subscribe）
- get_json_cache / set_json_cache：短 TTL JSON 缓存（供统计接口等高频读接口使用）
- delete_json_cache / delete_json_cache_pattern：删除单个或一组缓存键
"""

import json
import redis.asyncio as aioredis
from app.core.config import settings


def _redis_url(db: int = 2) -> str:
    auth = f":{settings.REDIS_PASSWORD}@" if settings.REDIS_PASSWORD else ""
    return f"redis://{auth}{settings.REDIS_HOST}:{settings.REDIS_PORT}/{db}"


def get_async_redis(db: int = 2) -> aioredis.Redis:
    """返回一个新的异步 Redis 连接（调用方负责关闭）"""
    timeout = settings.REDIS_CONNECT_TIMEOUT_SECONDS
    return aioredis.from_url(
        _redis_url(db),
        decode_responses=True,
        socket_connect_timeout=timeout,
        socket_timeout=timeout,
    )


async def close_async_redis(redis: aioredis.Redis) -> None:
    """Close Redis 5 async clients while keeping older type stubs quiet."""
    await redis.aclose()  # type: ignore[attr-defined]


async def publish_run_event(run_id: int, payload: dict, run_type: str = "case") -> None:
    """发布执行事件到按类型隔离的 Redis channel。

    ``TestRun`` 与 ``MobileSpecialRun`` 使用独立的数据表，ID 可能相同；
    将类型写入 channel 可以避免两个运行的实时消息互相串流。
    """
    if run_type not in {"case", "mobile"}:
        raise ValueError(f"unsupported run type: {run_type}")
    r = get_async_redis()
    try:
        await r.publish(f"atp:run:{run_type}:{run_id}", json.dumps(payload, ensure_ascii=False))
    finally:
        await close_async_redis(r)


async def get_json_cache(key: str, db: int = 2):
    r = get_async_redis(db)
    try:
        value = await r.get(key)
        return json.loads(value) if value else None
    finally:
        await close_async_redis(r)


async def set_json_cache(key: str, value, ttl_seconds: int = 300, db: int = 2) -> None:
    r = get_async_redis(db)
    try:
        await r.set(key, json.dumps(value, ensure_ascii=False), ex=ttl_seconds)
    finally:
        await close_async_redis(r)


async def delete_json_cache(key: str, db: int = 2) -> None:
    r = get_async_redis(db)
    try:
        await r.delete(key)
    finally:
        await close_async_redis(r)


async def delete_json_cache_pattern(pattern: str, db: int = 2) -> None:
    r = get_async_redis(db)
    try:
        keys = [key async for key in r.scan_iter(match=pattern)]
        if keys:
            await r.delete(*keys)
    finally:
        await close_async_redis(r)
