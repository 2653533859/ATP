from __future__ import annotations

import functools
import inspect
from collections.abc import Awaitable, Callable
from typing import TypeVar

T = TypeVar("T")
SerializedValue = object


def cached_json(
    *,
    key_builder: Callable[..., str],
    serializer: Callable[[T], SerializedValue],
    deserializer: Callable[[SerializedValue], T],
    read_cache: Callable[[str], Awaitable[SerializedValue | None]],
    write_cache: Callable[[str, SerializedValue], Awaitable[None]],
):
    """为异步函数提供 JSON 缓存包装。"""

    def decorator(func: Callable[..., Awaitable[T]]):
        signature = inspect.signature(func)

        @functools.wraps(func)
        async def wrapper(*args, **kwargs):
            bound = signature.bind_partial(*args, **kwargs)
            bound.apply_defaults()
            cache_key = key_builder(**bound.arguments)

            cached = await read_cache(cache_key)
            if cached is not None:
                return deserializer(cached)

            result = await func(*args, **kwargs)
            await write_cache(cache_key, serializer(result))
            return result

        return wrapper

    return decorator
