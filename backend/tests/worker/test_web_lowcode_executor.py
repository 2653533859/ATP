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


# ── run_web_lowcode 主执行链（fake Playwright 链 + MinIO/Redis 边界）──

from app.models.bootstrap import load_all_models  # noqa: E402
from app.models.case import RunStatus, StepResult  # noqa: E402

load_all_models()


class _Obj(types.SimpleNamespace):
    def __getattr__(self, name):
        return None


class _FakeDB:
    def __init__(self):
        self.added = []
        self.commits = 0

    def add(self, obj):
        self.added.append(obj)

    async def commit(self):
        self.commits += 1


class _RunPage(_FakePage):
    """在动作分发 fake 之上补 screenshot 能力。"""

    def __init__(self, *, screenshot_fails=False, **kw):
        super().__init__(**kw)
        self._screenshot_fails = screenshot_fails

    async def screenshot(self, type="png"):
        if self._screenshot_fails:
            raise RuntimeError("no display")
        return b"png-bytes"


class _FakeContext:
    def __init__(self, page, video_dir_holder, write_video=True):
        self._page = page
        self._holder = video_dir_holder
        self._write_video = write_video
        self.closed = False

    async def new_page(self):
        return self._page

    async def close(self):
        self.closed = True
        if self._write_video and self._holder.get("dir"):
            (Path(self._holder["dir"]) / "recording.webm").write_bytes(b"webm")


class _FakeBrowser:
    def __init__(self, context):
        self._context = context
        self.closed = False

    async def new_context(self, **kw):
        self.launch_context_kw = kw
        return self._context

    async def close(self):
        self.closed = True


class _FakePlaywright:
    def __init__(self, browser, launch_error=None):
        self._browser = browser
        self._launch_error = launch_error
        self.stopped = False
        self.chromium = types.SimpleNamespace(launch=self._launch)

    async def start(self):
        return self

    async def _launch(self, **kw):
        if self._launch_error:
            raise self._launch_error
        return self._browser

    async def stop(self):
        self.stopped = True


@pytest.fixture()
def wired(monkeypatch, tmp_path):
    """把 Playwright/MinIO/Redis/mkdtemp 全部接到可观测的 fake 上。"""
    events = []
    uploads = {"bytes": [], "files": []}
    holder = {"dir": str(tmp_path / "video")}
    Path(holder["dir"]).mkdir()

    async def fake_publish(run_id, payload):
        events.append(payload)

    monkeypatch.setattr(wlc, "publish_run_event", fake_publish)
    monkeypatch.setattr(wlc, "upload_bytes", lambda name, data, ct: uploads["bytes"].append((name, ct)))
    monkeypatch.setattr(wlc, "upload_file", lambda name, path, ct: uploads["files"].append((name, ct)))
    monkeypatch.setattr(wlc, "presigned_url", lambda name: f"https://minio/{name}")
    monkeypatch.setattr(wlc.tempfile, "mkdtemp", lambda prefix="": holder["dir"])
    return {"events": events, "uploads": uploads, "holder": holder}


def _wire_playwright(monkeypatch, page, holder, *, write_video=True, launch_error=None):
    context = _FakeContext(page, holder, write_video=write_video)
    browser = _FakeBrowser(context)
    pw = _FakePlaywright(browser, launch_error=launch_error)
    monkeypatch.setattr(wlc, "async_playwright", lambda: pw)
    return pw, browser, context


def _run_and_case(steps, run_id=7):
    run = _Obj(id=run_id, status=RunStatus.running, result_summary=None)
    case = _Obj(id=3, config={"steps": steps, "timeout": 5})
    return run, case


def test_run_web_lowcode_no_steps_marks_error(wired):
    db = _FakeDB()
    run, case = _run_and_case([])

    asyncio.run(wlc.run_web_lowcode(db, run, case, {}))

    assert run.status == RunStatus.error and "未配置任何步骤" in run.error_message
    assert db.commits == 1
    assert wired["events"][-1]["status"] == "error"


def test_run_web_lowcode_happy_path_with_screenshots_and_video(wired, monkeypatch):
    page = _RunPage()
    pw, browser, context = _wire_playwright(monkeypatch, page, wired["holder"])
    db = _FakeDB()
    run, case = _run_and_case(
        [
            {"action": "goto", "name": "打开", "params": {"url": "https://{{HOST}}/"}},
            {"action": "click", "params": {"selector": "#btn"}},
        ]
    )

    asyncio.run(wlc.run_web_lowcode(db, run, case, {"HOST": "example.com"}))

    assert run.status == RunStatus.passed and run.duration_ms is not None
    assert ("goto", "https://example.com/") in page.calls  # 变量替换生效
    step_rows = [o for o in db.added if isinstance(o, StepResult)]
    assert len(step_rows) == 2
    assert step_rows[0].screenshot_url == "https://minio/screenshots/runs/7/step_0.png"
    assert step_rows[1].name == "click_1"  # 未命名步骤按 action_idx 命名
    assert [n for n, _ in wired["uploads"]["bytes"]] == [
        "screenshots/runs/7/step_0.png",
        "screenshots/runs/7/step_1.png",
    ]
    # 录像在 context.close 后写入并上传
    assert context.closed and browser.closed and pw.stopped
    assert wired["uploads"]["files"] == [("videos/runs/7/recording.webm", "video/webm")]
    assert run.result_summary["video_url"] == "https://minio/videos/runs/7/recording.webm"
    completed = wired["events"][-1]
    assert completed["type"] == "completed" and completed["status"] == "passed"
    assert completed["video_url"].endswith("recording.webm")


def test_run_web_lowcode_failed_step_stops_and_marks_failed(wired, monkeypatch):
    page = _RunPage()
    _wire_playwright(monkeypatch, page, wired["holder"], write_video=False)
    db = _FakeDB()
    run, case = _run_and_case(
        [
            {"action": "teleport", "params": {}},  # 未知动作 → 失败
            {"action": "click", "params": {"selector": "#never"}},
        ]
    )

    asyncio.run(wlc.run_web_lowcode(db, run, case, {}))

    assert run.status == RunStatus.failed
    step_rows = [o for o in db.added if isinstance(o, StepResult)]
    assert len(step_rows) == 1  # 失败后中断，第二步未执行
    assert step_rows[0].status == RunStatus.failed and "未知操作类型" in step_rows[0].error_message
    assert ("click", "#never") not in page.calls
    assert run.result_summary in (None, {})  # 无录像不写 video_url
    assert wired["events"][-1]["status"] == "failed"


def test_run_web_lowcode_step_exception_recorded_and_truncated(wired, monkeypatch):
    class _BoomPage(_RunPage):
        async def click(self, selector, **kw):
            raise RuntimeError("x" * 3000)

    page = _BoomPage()
    _wire_playwright(monkeypatch, page, wired["holder"], write_video=False)
    db = _FakeDB()
    run, case = _run_and_case([{"action": "click", "params": {"selector": "#b"}}])

    asyncio.run(wlc.run_web_lowcode(db, run, case, {}))

    step = [o for o in db.added if isinstance(o, StepResult)][0]
    assert step.status == RunStatus.failed and len(step.error_message) == 2000  # 截断
    assert run.status == RunStatus.failed


def test_run_web_lowcode_launch_error_sets_error_message(wired, monkeypatch):
    _wire_playwright(
        monkeypatch, _RunPage(), wired["holder"], write_video=False, launch_error=RuntimeError("chromium missing")
    )
    db = _FakeDB()
    run, case = _run_and_case([{"action": "goto", "params": {"url": "https://x"}}])

    asyncio.run(wlc.run_web_lowcode(db, run, case, {}))

    assert run.status == RunStatus.failed and run.error_message == "chromium missing"
    assert [o for o in db.added if isinstance(o, StepResult)] == []
    assert wired["events"][-1]["status"] == "failed"


def test_take_screenshot_failure_returns_none(wired):
    url = asyncio.run(wlc._take_screenshot(_RunPage(screenshot_fails=True), 7, 0))
    assert url is None and wired["uploads"]["bytes"] == []


def test_safe_publish_swallows_publish_errors(monkeypatch):
    async def broken_publish(run_id, payload):
        raise RuntimeError("redis down")

    monkeypatch.setattr(wlc, "publish_run_event", broken_publish)
    asyncio.run(wlc._safe_publish(1, {"type": "x"}))  # 不抛异常即通过
