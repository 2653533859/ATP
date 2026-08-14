import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from app.worker import async_runner
from app.worker.async_runner import reset_worker_loop, run_async


async def _current_loop():
    return asyncio.get_running_loop()


async def _run_from_running_loop():
    current = asyncio.get_running_loop()
    result = run_async(_current_loop())
    return current, result


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


def test_run_async_uses_a_thread_when_called_from_running_loop():
    current, result = asyncio.run(_run_from_running_loop())

    assert result is not current


def test_create_worker_loop_uses_windows_proactor_policy(monkeypatch):
    created = object()

    class _FakePolicy:
        def new_event_loop(self):
            return created

    monkeypatch.setattr(async_runner.sys, "platform", "win32")
    monkeypatch.setitem(
        async_runner.asyncio.__dict__,
        "WindowsProactorEventLoopPolicy",
        lambda: _FakePolicy(),
    )

    assert async_runner._create_worker_loop() is created
