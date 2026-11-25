import asyncio
import logging
from typing import Any, Callable
from app.core.config import settings

logger = logging.getLogger(__name__)


class _PooledBrowser:
    def __init__(self, browser_name: str, headless: bool, pw: Any, browser: Any) -> None:
        self.browser_name = browser_name
        self.headless = headless
        self.pw = pw
        self.browser = browser
        # 累计分配过的上下文数：按生命周期计数、不随释放递减；达到上限后整个浏览器进程回收重建
        self.acquisitions = 0
        self.active_contexts = 0
        self.retired = False

    def is_healthy(self, max_acquisitions: int) -> bool:
        if self.retired or self.acquisitions >= max_acquisitions:
            return False
        is_conn = getattr(self.browser, "is_connected", None)
        if callable(is_conn):
            try:
                if not is_conn():
                    return False
            except Exception:
                return False
        elif hasattr(self.browser, "connected") and not self.browser.connected:
            return False
        return True

    async def close(self) -> None:
        try:
            if hasattr(self.browser, "close"):
                res = self.browser.close()
                if hasattr(res, "__await__"):
                    await res
        except Exception as e:
            logger.warning("Pooled browser close warning: %s", e)
        try:
            if hasattr(self.pw, "stop"):
                res = self.pw.stop()
                if hasattr(res, "__await__"):
                    await res
        except Exception as e:
            logger.warning("Pooled playwright driver stop warning: %s", e)


class BrowserContextPool:
    """Playwright 浏览器进程池与上下文管理器。

    在 Worker 进程中维护常驻 Browser 实例，消除每次测试用例启动 Chromium/Firefox/WebKit
    的冷启动（~1.5s）开销。为每个测试用例分配完全隔离的 BrowserContext（~20ms）。
    当累计分配的上下文数达到 WEB_BROWSER_POOL_MAX_CONTEXTS（类比 Celery 的
    worker_max_tasks_per_child，按生命周期计数、不随释放递减）或浏览器崩溃时，安全回收重建。
    """

    def __init__(self) -> None:
        self._pools: dict[tuple[str, bool], _PooledBrowser] = {}
        self._retired: dict[int, _PooledBrowser] = {}
        self._by_browser: dict[int, _PooledBrowser] = {}
        self._lock = asyncio.Lock()
        self._key_locks: dict[tuple[str, bool], asyncio.Lock] = {}

    def _lock_for(self, key: tuple[str, bool]) -> asyncio.Lock:
        lock = self._key_locks.get(key)
        if lock is None:
            lock = asyncio.Lock()
            self._key_locks[key] = lock
        return lock

    async def acquire_context(
        self,
        browser_name: str,
        headless: bool,
        context_options: dict[str, Any],
        *,
        async_playwright_fn: Callable[[], Any] | None = None,
    ) -> tuple[Any, Any, Any, bool]:
        """获取一个崭新且独立的 BrowserContext。

        返回 (browser_context, browser, pw, is_pooled)。
        """
        pooling_enabled = bool(getattr(settings, "WEB_BROWSER_POOLING_ENABLED", False))
        if not pooling_enabled:
            return await self._launch_standalone(browser_name, headless, context_options, async_playwright_fn)

        key = (browser_name, headless)
        to_close: list[_PooledBrowser] = []
        async with self._lock_for(key):
            max_acquisitions = int(getattr(settings, "WEB_BROWSER_POOL_MAX_CONTEXTS", 50))
            async with self._lock:
                pooled = self._pools.get(key)
                if pooled is not None and not pooled.is_healthy(max_acquisitions):
                    pooled.retired = True
                    self._pools.pop(key, None)
                    if pooled.active_contexts <= 0:
                        self._by_browser.pop(id(pooled.browser), None)
                        to_close.append(pooled)
                    else:
                        self._retired[id(pooled.browser)] = pooled
                    pooled = None
            if pooled is None:
                pw, browser = await self._launch_browser(browser_name, headless, async_playwright_fn)
                pooled = _PooledBrowser(browser_name, headless, pw, browser)
                async with self._lock:
                    self._pools[key] = pooled
                    self._by_browser[id(browser)] = pooled

            async with self._lock:
                pooled.acquisitions += 1
                pooled.active_contexts += 1
                browser = pooled.browser
                pw = pooled.pw

        try:
            browser_context = await browser.new_context(**context_options)
        except Exception as exc:
            logger.warning("Failed to create context on pooled browser, recycling: %s", exc)
            async with self._lock:
                pooled.active_contexts = max(0, pooled.active_contexts - 1)
                pooled.retired = True
                if self._pools.get(key) is pooled:
                    self._pools.pop(key, None)
                if pooled.active_contexts <= 0:
                    self._by_browser.pop(id(pooled.browser), None)
                    to_close.append(pooled)
                else:
                    self._retired[id(pooled.browser)] = pooled
            for retired_browser in to_close:
                await retired_browser.close()
            return await self._launch_standalone(browser_name, headless, context_options, async_playwright_fn)

        for retired_browser in to_close:
            await retired_browser.close()
        return browser_context, browser, pw, True

    async def release_context(
        self,
        browser_context: Any | None,
        browser: Any | None,
        pw: Any | None,
        is_pooled: bool,
    ) -> None:
        """安全释放与关闭 BrowserContext。若非池化或已崩溃则级联关闭 Browser。"""
        if browser_context is not None:
            try:
                if hasattr(browser_context, "close"):
                    res = browser_context.close()
                    if hasattr(res, "__await__"):
                        await res
            except Exception as e:
                logger.warning("BrowserContext close warning: %s", e)

        is_crashed = False
        if browser is not None:
            is_conn = getattr(browser, "is_connected", None)
            if callable(is_conn):
                try:
                    if not is_conn():
                        is_crashed = True
                except Exception:
                    is_crashed = True
            elif hasattr(browser, "connected") and not self._is_connected_safe(browser):
                is_crashed = True

        if is_pooled and browser is not None:
            pooled_to_close: _PooledBrowser | None = None
            async with self._lock:
                pooled = self._by_browser.get(id(browser))
                if pooled is not None:
                    pooled.active_contexts = max(0, pooled.active_contexts - 1)
                    if is_crashed or (pooled.retired and pooled.active_contexts <= 0):
                        pooled.retired = True
                        for k, current in list(self._pools.items()):
                            if current is pooled:
                                self._pools.pop(k, None)
                                break
                        if pooled.active_contexts <= 0:
                            self._retired.pop(id(browser), None)
                            self._by_browser.pop(id(browser), None)
                            pooled_to_close = pooled
                        else:
                            self._retired[id(browser)] = pooled
            if pooled_to_close is not None:
                await pooled_to_close.close()
            return

        if not is_pooled or is_crashed:
            if browser is not None:
                try:
                    if hasattr(browser, "close"):
                        res = browser.close()
                        if hasattr(res, "__await__"):
                            await res
                except Exception as e:
                    logger.warning("Browser close warning: %s", e)
            if pw is not None:
                try:
                    if hasattr(pw, "stop"):
                        res = pw.stop()
                        if hasattr(res, "__await__"):
                            await res
                except Exception as e:
                    logger.warning("Playwright stop warning: %s", e)

    @staticmethod
    def _is_connected_safe(browser: Any) -> bool:
        return bool(getattr(browser, "connected", True))

    async def _launch_browser(
        self,
        browser_name: str,
        headless: bool,
        async_playwright_fn: Callable[[], Any] | None,
    ) -> tuple[Any, Any]:
        if async_playwright_fn is None:
            from playwright.async_api import async_playwright

            async_playwright_fn = async_playwright
        pw_raw = async_playwright_fn()
        if hasattr(pw_raw, "start"):
            pw = await pw_raw.start()
        else:
            pw = pw_raw
        browser_launcher = getattr(pw, browser_name)
        launch_options: dict[str, Any] = {"headless": headless}
        if browser_name == "chromium":
            launch_options["args"] = ["--no-sandbox"]
        browser = await browser_launcher.launch(**launch_options)
        return pw, browser

    async def _launch_standalone(
        self,
        browser_name: str,
        headless: bool,
        context_options: dict[str, Any],
        async_playwright_fn: Callable[[], Any] | None,
    ) -> tuple[Any, Any, Any, bool]:
        pw, browser = await self._launch_browser(browser_name, headless, async_playwright_fn)
        try:
            browser_context = await browser.new_context(**context_options)
        except Exception:
            try:
                if hasattr(browser, "close"):
                    res = browser.close()
                    if hasattr(res, "__await__"):
                        await res
            except Exception:
                pass
            try:
                if hasattr(pw, "stop"):
                    res = pw.stop()
                    if hasattr(res, "__await__"):
                        await res
            except Exception:
                pass
            raise
        return browser_context, browser, pw, False

    async def close_all(self) -> None:
        """关闭所有池化的 Browser 进程（在 Worker 退出或测试清理时调用）。"""
        async with self._lock:
            to_close = list(self._pools.values()) + list(self._retired.values())
            self._pools.clear()
            self._retired.clear()
            self._by_browser.clear()
        for pooled in to_close:
            await pooled.close()


# 全局单例
browser_pool = BrowserContextPool()
acquire_browser_context = browser_pool.acquire_context
release_browser_context = browser_pool.release_context
close_all_browsers = browser_pool.close_all
