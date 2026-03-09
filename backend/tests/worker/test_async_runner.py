import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from app.worker.async_runner import reset_worker_loop, run_async


async def _current_loop():
    return asyncio.get_running_loop()


def teardown_function():
    reset_worker_loop()


def test_run_async_reuses_cached_loop():
    first = run_async(_current_loop())
    second = run_async(_current_loop())

    assert first is second


def test_run_async_recreates_closed_loop():
    first = run_async(_current_loop())
    reset_worker_loop()

    second = run_async(_current_loop())

    assert first is not second
