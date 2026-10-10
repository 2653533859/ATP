import asyncio
from app.core.config import settings
from app.services.browser_pool import BrowserContextPool
import pytest


@pytest.fixture(autouse=True)
def enable_pooling():
    old_val = getattr(settings, "WEB_BROWSER_POOLING_ENABLED", False)
    setattr(settings, "WEB_BROWSER_POOLING_ENABLED", True)
    try:
        yield
    finally:
        setattr(settings, "WEB_BROWSER_POOLING_ENABLED", old_val)


class _FakeContext:
    def __init__(self):
        self.closed = False

    async def close(self):
        self.closed = True


class _FakeBrowser:
    def __init__(self, name="chromium"):
        self.name = name
        self.closed = False
        self.connected = True
        self.contexts = []

    def is_connected(self):
        return self.connected

    async def new_context(self, **kwargs):
        ctx = _FakeContext()
        self.contexts.append((ctx, kwargs))
        return ctx

    async def close(self):
        self.closed = True


class _FakePlaywright:
    def __init__(self, browser_factory=None):
        self.stopped = False
        self.browser_factory = browser_factory or (lambda: _FakeBrowser())
        self.browsers = []

    async def start(self):
        return self

    def __getattr__(self, _name: str):
        async def launch(*_args, **_kwargs):
            b = self.browser_factory()
            self.browsers.append(b)
            return b

        return type("Launcher", (), {"launch": launch})()

    async def stop(self):
        self.stopped = True


def test_browser_pool_reuses_browser_for_same_engine():
    pool = BrowserContextPool()
    pw_instance = _FakePlaywright()

    async def _run():
        # First acquire launches browser 1
        ctx1, b1, pw1, is_pooled1 = await pool.acquire_context(
            "chromium", True, {"viewport": {"width": 1280, "height": 720}}, async_playwright_fn=lambda: pw_instance
        )
        assert is_pooled1
        assert len(pw_instance.browsers) == 1

        # Release context 1 (browser remains open)
        await pool.release_context(ctx1, b1, pw1, is_pooled1)
        assert ctx1.closed
        assert not b1.closed

        # Second acquire reuses browser 1
        ctx2, b2, pw2, is_pooled2 = await pool.acquire_context(
            "chromium", True, {"viewport": {"width": 1440, "height": 900}}, async_playwright_fn=lambda: pw_instance
        )
        assert is_pooled2
        assert b2 is b1
        assert len(pw_instance.browsers) == 1

        await pool.release_context(ctx2, b2, pw2, is_pooled2)
        assert ctx2.closed
        assert not b2.closed

        # Clean shutdown
        await pool.close_all()
        assert b1.closed

    asyncio.run(_run())


def test_browser_pool_recovers_on_crash():
    pool = BrowserContextPool()
    pw_instance = _FakePlaywright()

    async def _run():
        ctx1, b1, pw1, is_pooled1 = await pool.acquire_context(
            "chromium", True, {}, async_playwright_fn=lambda: pw_instance
        )
        assert len(pw_instance.browsers) == 1

        # Simulate browser crash during test
        b1.connected = False

        # Release should detect crash and close browser & evict from pool
        await pool.release_context(ctx1, b1, pw1, is_pooled1)
        assert ctx1.closed
        assert b1.closed

        # Next acquire automatically launches fresh browser 2
        ctx2, b2, pw2, is_pooled2 = await pool.acquire_context(
            "chromium", True, {}, async_playwright_fn=lambda: pw_instance
        )
        assert len(pw_instance.browsers) == 2
        assert b2 is not b1
        assert not b2.closed

        await pool.close_all()
        assert b2.closed

    asyncio.run(_run())


def test_browser_pool_recycles_after_max_tasks():
    pool = BrowserContextPool()
    pw_instance = _FakePlaywright()

    async def _run():
        # Set max tasks to 2
        from app.core.config import settings

        original_max = settings.WEB_BROWSER_POOL_MAX_CONTEXTS
        settings.WEB_BROWSER_POOL_MAX_CONTEXTS = 2
        try:
            # Task 1
            ctx1, b1, pw1, _ = await pool.acquire_context("firefox", True, {}, async_playwright_fn=lambda: pw_instance)
            await pool.release_context(ctx1, b1, pw1, True)

            # Task 2 (reuses b1)
            ctx2, b2, pw2, _ = await pool.acquire_context("firefox", True, {}, async_playwright_fn=lambda: pw_instance)
            assert b2 is b1
            await pool.release_context(ctx2, b2, pw2, True)

            # Task 3 (exceeded max_contexts 2 -> recycles b1 and launches b2)
            ctx3, b3, pw3, _ = await pool.acquire_context("firefox", True, {}, async_playwright_fn=lambda: pw_instance)
            assert b3 is not b1
            assert b1.closed
            assert len(pw_instance.browsers) == 2

            await pool.close_all()
            assert b3.closed
        finally:
            settings.WEB_BROWSER_POOL_MAX_CONTEXTS = original_max

    asyncio.run(_run())
