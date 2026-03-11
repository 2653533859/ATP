import asyncio
import sys
from collections.abc import Awaitable
from typing import TypeVar

T = TypeVar("T")

_worker_loop: asyncio.AbstractEventLoop | None = None


def _create_worker_loop() -> asyncio.AbstractEventLoop:
    if sys.platform == "win32":
        proactor_policy = getattr(asyncio, "WindowsProactorEventLoopPolicy", None)
        if proactor_policy is not None:
            return proactor_policy().new_event_loop()

    return asyncio.new_event_loop()


def run_async(coro: Awaitable[T]) -> T:
    """Run worker coroutines on a stable event loop per process."""
    global _worker_loop

    if _worker_loop is None or _worker_loop.is_closed():
        _worker_loop = _create_worker_loop()

    asyncio.set_event_loop(_worker_loop)
    return _worker_loop.run_until_complete(coro)


def reset_worker_loop() -> None:
    """Test helper to close the cached worker loop."""
    global _worker_loop

    if _worker_loop is not None and not _worker_loop.is_closed():
        _worker_loop.close()
    _worker_loop = None
