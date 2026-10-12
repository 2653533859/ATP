"""worker_process_shutdown 必须回收池化浏览器，避免 worker 退出后残留 Chromium/Playwright 子进程。"""

import pytest

pytest.importorskip("celery")

from app.core.config import settings
from app.services import browser_pool
from app.worker import celery_app as celery_module
from app.worker.async_runner import reset_worker_loop, run_async


class _FakeContext:
    async def close(self) -> None:
        return None


class _FakeBrowser:
    def __init__(self) -> None:
        self.closed = False

    def is_connected(self) -> bool:
        return not self.closed

    async def new_context(self, **_kwargs):
        return _FakeContext()

    async def close(self) -> None:
        self.closed = True


class _FakePlaywright:
    def __init__(self) -> None:
        self.stopped = False
        self.browsers: list[_FakeBrowser] = []

    async def start(self):
        return self

    def __getattr__(self, _name: str):
        async def launch(*_args, **_kwargs):
            browser = _FakeBrowser()
            self.browsers.append(browser)
            return browser

        return type("Launcher", (), {"launch": launch})()

    async def stop(self) -> None:
        self.stopped = True


@pytest.fixture(autouse=True)
def _fresh_worker_loop():
    reset_worker_loop()
    yield
    reset_worker_loop()


def test_worker_process_shutdown_closes_browser_pool(monkeypatch):
    closed = []

    async def _fake_close_all() -> None:
        closed.append(True)

    monkeypatch.setattr(browser_pool, "close_all_browsers", _fake_close_all)

    celery_module._shutdown_browser_pool()

    assert closed == [True]


def test_worker_process_shutdown_swallows_pool_errors(monkeypatch):
    async def _boom() -> None:
        raise RuntimeError("driver already gone")

    monkeypatch.setattr(browser_pool, "close_all_browsers", _boom)

    # 关闭失败只记日志，不能拖垮 worker 退出流程
    celery_module._shutdown_browser_pool()


def test_worker_process_shutdown_closes_pooled_browser_on_worker_loop(monkeypatch):
    """浏览器在 worker loop 上创建，关闭也必须回到同一个 loop 才能真正落到 Playwright。"""
    monkeypatch.setattr(settings, "WEB_BROWSER_POOLING_ENABLED", True)
    pool = browser_pool.BrowserContextPool()
    monkeypatch.setattr(browser_pool, "close_all_browsers", pool.close_all)
    playwright = _FakePlaywright()

    async def _acquire_and_release() -> None:
        ctx, browser, pw, is_pooled = await pool.acquire_context(
            "chromium", True, {}, async_playwright_fn=lambda: playwright
        )
        assert is_pooled
        await pool.release_context(ctx, browser, pw, is_pooled)

    run_async(_acquire_and_release())
    assert playwright.browsers and not playwright.browsers[0].closed

    celery_module._shutdown_browser_pool()

    assert playwright.browsers[0].closed
    assert playwright.stopped
