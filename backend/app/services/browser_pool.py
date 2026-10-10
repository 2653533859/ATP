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
        self.context_count = 0

    def is_healthy(self, max_contexts: int) -> bool:
        if self.context_count >= max_contexts:
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
    并在达到最大上下文数或发生崩溃时安全回收重构。
    """

    def __init__(self) -> None:
        self._pools: dict[tuple[str, bool], _PooledBrowser] = {}
        self._lock = asyncio.Lock()

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
        async with self._lock:
            max_contexts = int(getattr(settings, "WEB_BROWSER_POOL_MAX_CONTEXTS", 50))
            pooled = self._pools.get(key)
            if pooled is not None and not pooled.is_healthy(max_contexts):
                await pooled.close()
                pooled = None
                self._pools.pop(key, None)
            if pooled is None:
                pw, browser = await self._launch_browser(browser_name, headless, async_playwright_fn)
                pooled = _PooledBrowser(browser_name, headless, pw, browser)
                self._pools[key] = pooled

            pooled.context_count += 1
            browser = pooled.browser
            pw = pooled.pw

            try:
                browser_context = await browser.new_context(**context_options)
                return browser_context, browser, pw, True
            except Exception as exc:
                logger.warning("Failed to create context on pooled browser, recycling: %s", exc)
                await pooled.close()
                self._pools.pop(key, None)
                return await self._launch_standalone(browser_name, headless, context_options, async_playwright_fn)

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

        if not is_pooled or is_crashed:
            if is_crashed:
                async with self._lock:
                    for k, pooled in list(self._pools.items()):
                        if pooled.browser is browser:
                            self._pools.pop(k, None)
                            break
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
        browser_context = await browser.new_context(**context_options)
        return browser_context, browser, pw, False

    async def close_all(self) -> None:
        """关闭所有池化的 Browser 进程（在 Worker 退出或测试清理时调用）。"""
        async with self._lock:
            for pooled in list(self._pools.values()):
                await pooled.close()
            self._pools.clear()


# 全局单例
browser_pool = BrowserContextPool()
acquire_browser_context = browser_pool.acquire_context
release_browser_context = browser_pool.release_context
close_all_browsers = browser_pool.close_all
