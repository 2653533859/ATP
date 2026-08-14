import asyncio
import sys
import threading
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


def _run_in_new_thread(coro: Awaitable[T]) -> T:
    """Run a coroutine outside a currently running worker loop.

    Celery can dispatch the periodic Android heartbeat while another task is
    using the process-wide worker loop.  A second loop in a short-lived thread
    avoids re-entering ``run_until_complete`` and keeps the synchronous Celery
    task interface intact.
    """
    result: list[T] = []
    error: list[BaseException] = []

    def runner() -> None:
        loop = _create_worker_loop()
        try:
            asyncio.set_event_loop(loop)
            result.append(loop.run_until_complete(coro))
        except BaseException as exc:  # propagate the original task failure
            error.append(exc)
        finally:
            try:
                loop.run_until_complete(loop.shutdown_asyncgens())
            except Exception:
                pass
            loop.close()
            asyncio.set_event_loop(None)

    thread = threading.Thread(target=runner, name="atp-async-task", daemon=True)
    thread.start()
    thread.join()
    if error:
        raise error[0]
    return result[0]


def run_async(coro: Awaitable[T]) -> T:
    """Run worker coroutines on a stable event loop per process."""
    global _worker_loop

    try:
        running_loop = asyncio.get_running_loop()
    except RuntimeError:
        running_loop = None

    if running_loop is not None or (_worker_loop is not None and _worker_loop.is_running()):
        return _run_in_new_thread(coro)

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
