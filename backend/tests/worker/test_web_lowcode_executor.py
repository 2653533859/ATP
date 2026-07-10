"""web_lowcode_executor 单元缝测试：_execute_step 动作分发用 fake Page 记录调用，
_replace_vars / _replace_vars_in_params 变量替换走真实现。"""

import asyncio
import sys
import types
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

# 其它测试可能把 app.core.minio_client 换成缺字段的 stub；导入执行器前补齐所需符号
_minio = sys.modules.setdefault("app.core.minio_client", types.SimpleNamespace())
for _name in ("upload_bytes", "upload_file", "presigned_url"):
    if not hasattr(_minio, _name):
        setattr(_minio, _name, lambda *a, **kw: None)

from app.worker.executors import web_lowcode_executor as wlc  # noqa: E402


class _FakePage:
    """记录被调用的 Playwright 动作，可脚本化 inner_text / locator 行为。"""

    def __init__(self, *, body_text="", locator_visible=True):
        self.url = "https://app.example.com/after"
        self.calls = []
        self._body_text = body_text
        self._locator_visible = locator_visible
        self.keyboard = types.SimpleNamespace(press=self._kb_press)

    async def goto(self, url, **kw):
        self.calls.append(("goto", url))

    async def click(self, selector, **kw):
        self.calls.append(("click", selector))

    async def fill(self, selector, value, **kw):
        self.calls.append(("fill", selector, value))

    async def select_option(self, selector, value, **kw):
        self.calls.append(("select", selector, value))

    async def press(self, selector, key, **kw):
        self.calls.append(("press", selector, key))

    async def _kb_press(self, key):
        self.calls.append(("kb_press", key))

    async def hover(self, selector, **kw):
        self.calls.append(("hover", selector))

    async def inner_text(self, _sel):
        return self._body_text

    def locator(self, selector):
        page = self

        class _Loc:
            async def wait_for(self, **kw):
                if not page._locator_visible:
                    raise RuntimeError("not visible")

        return _Loc()


def _step(action, **params):
    return asyncio.run(wlc._execute_step(_FakePage(), action, params, 5000))


# ── 变量替换 ────────────────────────────────────────────────


def test_replace_vars_substitutes_known_and_keeps_unknown():
    ctx = {"USER": "amy", "HOST": "example.com"}
    assert wlc._replace_vars("{{USER}}@{{HOST}}", ctx) == "amy@example.com"
    assert wlc._replace_vars("{{MISSING}}", ctx) == "{{MISSING}}"
    assert wlc._replace_vars("", ctx) == ""


def test_replace_vars_in_params_recurses_and_preserves_non_strings():
    ctx = {"ID": "42"}
    result = wlc._replace_vars_in_params({"url": "/u/{{ID}}", "nested": {"q": "{{ID}}", "n": 7}, "flag": True}, ctx)
    assert result == {"url": "/u/42", "nested": {"q": "42", "n": 7}, "flag": True}


# ── 动作分发 ────────────────────────────────────────────────


def test_execute_step_navigation_and_input_actions():
    page = _FakePage()
    assert asyncio.run(wlc._execute_step(page, "goto", {"url": "https://x"}, 5000)) == {
        "success": True,
        "data": {"url": page.url},
    }
    assert asyncio.run(wlc._execute_step(page, "click", {"selector": "#btn"}, 5000)) == {"success": True}
    assert asyncio.run(wlc._execute_step(page, "fill", {"selector": "#u", "value": "amy"}, 5000)) == {"success": True}
    assert asyncio.run(wlc._execute_step(page, "select", {"selector": "#s", "value": "v"}, 5000)) == {"success": True}
    assert asyncio.run(wlc._execute_step(page, "hover", {"selector": "#h"}, 5000)) == {"success": True}
    assert ("goto", "https://x") in page.calls
    assert ("fill", "#u", "amy") in page.calls


def test_execute_step_press_with_and_without_selector():
    page = _FakePage()
    asyncio.run(wlc._execute_step(page, "press", {"selector": "#i", "key": "Tab"}, 5000))
    asyncio.run(wlc._execute_step(page, "press", {"key": "Enter"}, 5000))
    assert ("press", "#i", "Tab") in page.calls
    assert ("kb_press", "Enter") in page.calls


def test_execute_step_assert_text_visible_or_body_fallback():
    # locator 可见 → success
    assert asyncio.run(wlc._execute_step(_FakePage(locator_visible=True), "assert_text", {"text": "hi"}, 5000)) == {
        "success": True
    }
    # locator 不可见但 body 含文本 → success（兜底）
    page = _FakePage(locator_visible=False, body_text="welcome hi there")
    assert asyncio.run(wlc._execute_step(page, "assert_text", {"text": "hi"}, 5000)) == {"success": True}
    # locator 不可见且 body 不含 → 失败
    page = _FakePage(locator_visible=False, body_text="nothing")
    result = asyncio.run(wlc._execute_step(page, "assert_text", {"text": "missing"}, 5000))
    assert result["success"] is False and "未找到文本" in result["error"]


def test_execute_step_assert_visible_success_and_failure():
    assert asyncio.run(
        wlc._execute_step(_FakePage(locator_visible=True), "assert_visible", {"selector": "#ok"}, 5000)
    ) == {"success": True}
    result = asyncio.run(
        wlc._execute_step(_FakePage(locator_visible=False), "assert_visible", {"selector": "#no"}, 5000)
    )
    assert result["success"] is False and "不可见" in result["error"]


def test_execute_step_wait_screenshot_and_unknown_action(monkeypatch):
    slept = []

    async def fake_sleep(seconds):
        slept.append(seconds)

    monkeypatch.setattr(wlc.asyncio, "sleep", fake_sleep)
    assert asyncio.run(wlc._execute_step(_FakePage(), "wait", {"ms": 250}, 5000)) == {"success": True}
    assert slept == [0.25]

    assert asyncio.run(wlc._execute_step(_FakePage(), "screenshot", {}, 5000)) == {
        "success": True,
        "data": {"manual_screenshot": True},
    }

    result = asyncio.run(wlc._execute_step(_FakePage(), "teleport", {}, 5000))
    assert result["success"] is False and "未知操作类型" in result["error"]


def test_format_exception_message_uses_type_when_blank():
    assert wlc._format_exception_message(ValueError("boom")) == "boom"
    assert wlc._format_exception_message(RuntimeError("")) == "RuntimeError"
