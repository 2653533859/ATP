"""web_lowcode_executor 覆盖率补齐：单元分支 + run_web_lowcode 主流程/矩阵（全 fake，无真实浏览器）。

仅新建文件，不改动源码与既有测试；Playwright/MinIO/Redis 均以 fake 隔离。
"""

import asyncio
import json
import tempfile
import types
from pathlib import Path

import pytest

from app.models.bootstrap import load_all_models

load_all_models()

from app.models.case import RunStatus  # noqa: E402
from app.worker.executors import web_lowcode_executor as wlc  # noqa: E402


class _FakeLocator:
    def __init__(self, page, selector):
        self.page = page
        self.selector = selector

    async def wait_for(self, state=None, timeout=None):
        behavior = self.page.locator_behavior.get(self.selector, True)
        if behavior is False:
            raise TimeoutError(f"locator not found: {self.selector}")
        if isinstance(behavior, Exception):
            raise behavior
        return True

    async def inner_text(self):
        return self.page.locator_text.get(self.selector, self.page.body_text)

    async def screenshot(self, timeout=None):
        return self.page.screenshot_bytes


class _FakeKeyboard:
    def __init__(self, page):
        self.page = page

    async def press(self, key):
        self.page.keyboard_presses.append(key)


class _FakePage:
    def __init__(
        self, *, body_text="", screenshot_bytes=b"PNG", url="https://page.test/", context=None, support_download=True
    ):
        self.body_text = body_text
        self.screenshot_bytes = screenshot_bytes
        self.url = url
        self.context = context
        self.locator_behavior = {}
        self.locator_text = {}
        self.clicks = []
        self.fills = []
        self.gotos = []
        self.selects = []
        self.presses = []
        self.hovers = []
        self.uploaded_files = []
        self.keyboard_presses = []
        self.keyboard = _FakeKeyboard(self)
        self.handlers = {}
        self.expect_download_cm = None
        if not support_download:
            self.expect_download = None

    def locator(self, selector):
        return _FakeLocator(self, selector)

    async def goto(self, url, timeout=None, wait_until=None):
        self.gotos.append(url)
        self.url = url
        handler = getattr(self.context, "route_handler", None)
        if handler is not None:
            await handler(types.SimpleNamespace(url=url))

    async def click(self, selector, timeout=None):
        behavior = self.locator_behavior.get(selector, True)
        if isinstance(behavior, Exception):
            raise behavior
        self.clicks.append(selector)

    async def fill(self, selector, value, timeout=None):
        self.fills.append((selector, value))

    async def inner_text(self, selector):
        return self.body_text

    async def select_option(self, selector, value, timeout=None):
        self.selects.append((selector, value))

    async def press(self, selector, key, timeout=None):
        self.presses.append((selector, key))

    async def hover(self, selector, timeout=None):
        self.hovers.append(selector)

    async def screenshot(self, type=None, timeout=None):
        return self.screenshot_bytes

    async def set_input_files(self, selector, path, timeout=None):
        self.uploaded_files.append((selector, path))

    def expect_download(self, timeout=None):
        return self.expect_download_cm

    def on(self, event, handler):
        self.handlers.setdefault(event, []).append(handler)

    def emit(self, event, payload):
        for handler in self.handlers.get(event, []):
            handler(payload)


class _FakeTracing:
    def __init__(self, *, write_on_stop=False, stop_error=None):
        self.started = False
        self.stopped = False
        self.start_kwargs = None
        self.write_on_stop = write_on_stop
        self.stop_error = stop_error

    async def start(self, **kwargs):
        self.started = True
        self.start_kwargs = kwargs

    async def stop(self, path=None):
        self.stopped = True
        if self.stop_error is not None:
            raise self.stop_error
        if self.write_on_stop and path:
            Path(path).write_bytes(b"zip")


class _FakeBrowserContext:
    def __init__(self, *, page=None, tracing=None, storage_state_value=None, storage_state_error=None):
        self.page = page
        self.tracing = tracing
        self.storage_state_value = {"cookies": []} if storage_state_value is None else storage_state_value
        self.storage_state_error = storage_state_error
        self.route_handler = None
        self.route_calls = []

    async def route(self, pattern, handler):
        self.route_calls.append(pattern)
        self.route_handler = handler

    async def new_page(self):
        if self.page is None:
            self.page = _FakePage(context=self)
        return self.page

    async def storage_state(self):
        if self.storage_state_error is not None:
            raise self.storage_state_error
        return self.storage_state_value


class _FakeBrowser:
    def __init__(self, connected=True):
        self.connected = connected

    def is_connected(self):
        return self.connected


class _FakeDownload:
    def __init__(self, path, suggested_filename="report.csv"):
        self._path = path
        self.suggested_filename = suggested_filename

    async def path(self):
        return self._path


class _ExpectDownloadCM:
    def __init__(self, download):
        self._download = download

    async def __aenter__(self):
        future = asyncio.get_running_loop().create_future()
        future.set_result(self._download)
        return types.SimpleNamespace(value=future)

    async def __aexit__(self, *exc):
        return False


def _install_web_env(
    monkeypatch,
    *,
    page=None,
    tracing=None,
    browser=None,
    is_pooled=False,
    write_video=False,
    storage_state_value=None,
    storage_state_error=None,
):
    """隔离浏览器/MinIO/Redis/自愈器等全部外部依赖，返回可断言的 events。"""
    events = types.SimpleNamespace(
        published=[],
        uploaded=[],
        upload_files=[],
        released=[],
        reset_runs=[],
        cleared=[],
        acquire_kwargs=None,
        guard_calls=[],
    )
    page = _FakePage() if page is None else page
    context = _FakeBrowserContext(
        page=page, tracing=tracing, storage_state_value=storage_state_value, storage_state_error=storage_state_error
    )
    page.context = context
    browser = _FakeBrowser() if browser is None else browser

    async def _acquire(**kwargs):
        events.acquire_kwargs = kwargs
        video_dir = (kwargs.get("context_options") or {}).get("record_video_dir")
        if write_video and video_dir:
            (Path(video_dir) / "video.webm").write_bytes(b"vid")
        return context, browser, "pw-handle", is_pooled

    async def _release(ctx, br, pw_arg, pooled):
        events.released.append((ctx, br, pw_arg, pooled))

    async def _publish(run_id, payload):
        events.published.append(payload)

    async def _guard(route, blocked):
        events.guard_calls.append(getattr(route, "url", None))
        return True

    async def _heal(page_arg, action, params, timeout_ms, **kwargs):
        events.healed = True
        return {"success": True, "data": {"healed": True}}

    monkeypatch.setattr(wlc, "build_web_matrix", lambda cfg: [{}])
    monkeypatch.setattr(wlc, "acquire_browser_context", _acquire)
    monkeypatch.setattr(wlc, "release_browser_context", _release)
    monkeypatch.setattr(wlc, "publish_run_event", _publish)
    monkeypatch.setattr(wlc, "upload_bytes", lambda name, data, ct: events.uploaded.append((name, data, ct)))
    monkeypatch.setattr(wlc, "upload_file", lambda name, path, ct: events.upload_files.append((name, str(path), ct)))
    monkeypatch.setattr(wlc, "download_file", lambda name, path: Path(path).write_bytes(b"file-bytes"))
    monkeypatch.setattr(wlc, "read_bytes", lambda name: b'{"cookies": []}')
    monkeypatch.setattr(wlc, "presigned_url", lambda name, expires_seconds=None: f"https://minio/{name}")
    monkeypatch.setattr(wlc, "is_cancel_requested", lambda run_id: False)
    monkeypatch.setattr(wlc, "clear_cancel_request", lambda run_id: events.cleared.append(run_id))
    monkeypatch.setattr(wlc, "guard_browser_request", _guard)
    monkeypatch.setattr(wlc, "is_locator_failure", lambda message: False)
    monkeypatch.setattr(
        wlc,
        "runtime_locator_healer",
        types.SimpleNamespace(attempt_heal_and_retry=_heal, reset_run=lambda rid: events.reset_runs.append(rid)),
    )
    return events, page, context


class _RunDB:
    def __init__(self, *, module=None, page_object=None, element_asset=None, visual_baseline=None):
        self.module = module if module is not None else types.SimpleNamespace(project_id=5)
        self.page_object = page_object
        self.element_asset = element_asset
        self.visual_baseline = visual_baseline
        self.added = []
        self.commits = 0
        self.flushes = 0
        self._next_id = 500

    async def get(self, model, pk):
        if model is wlc.Module:
            return self.module
        if model is wlc.WebPageObject:
            return self.page_object
        if model is wlc.WebElementAsset:
            return self.element_asset
        if model is wlc.WebVisualBaseline:
            return self.visual_baseline
        return None

    def add(self, item):
        self.added.append(item)
        if getattr(item, "id", None) is None:
            item.id = self._next_id
            self._next_id += 1

    async def flush(self):
        self.flushes += 1

    async def commit(self):
        self.commits += 1


def _run_entities(steps=None, *, cfg=None, run_id=99, project_id=5):
    config = dict(cfg or {})
    if steps is not None:
        config["steps"] = steps
    run = types.SimpleNamespace(
        id=run_id,
        status=RunStatus.running,
        error_message=None,
        duration_ms=None,
        result_summary=None,
        triggered_by=1,
        trace_id="trace-1",
        environment="prod",
    )
    case = types.SimpleNamespace(id=7, module_id=22, config=config)
    db = _RunDB(module=types.SimpleNamespace(project_id=project_id))
    return db, run, case


def test_await_with_cancel_detects_disconnected_browser(monkeypatch):
    monkeypatch.setattr(wlc, "is_cancel_requested", lambda run_id: False)

    class _DeadBrowser:
        def is_connected(self):
            return False

    async def _run():
        try:
            await wlc._await_with_cancel(5, asyncio.sleep(30), _DeadBrowser())
        except RuntimeError as exc:
            return str(exc)
        raise AssertionError("expected RuntimeError")

    assert "浏览器进程已断开" in asyncio.run(_run())


def test_locator_to_selector_variants():
    assert wlc._locator_to_selector({"strategy": "css"}) == ""
    assert wlc._locator_to_selector({"strategy": "css", "value": "  #a "}) == "#a"
    assert wlc._locator_to_selector({"strategy": "xpath", "value": "//a"}) == "xpath=//a"
    assert wlc._locator_to_selector({"strategy": "role", "value": "button"}) == "role=button"
    assert (
        wlc._locator_to_selector({"strategy": "role", "value": "button", "name": 'Say "hi"'})
        == 'role=button[name="Say \\"hi\\""]'
    )
    assert wlc._locator_to_selector({"strategy": "test_id", "value": 'a"b'}) == '[data-testid="a\\"b"]'
    assert wlc._locator_to_selector({"strategy": "weird", "value": "raw"}) == "raw"


def test_asset_selectors_collects_fallback_locators():
    asset = types.SimpleNamespace(
        locator={"strategy": "css", "value": "#main"},
        fallback_locators=[{"strategy": "xpath", "value": "//x"}, "not-a-dict", {"strategy": "css", "value": ""}],
    )
    assert wlc._asset_selectors(asset) == ["#main", "xpath=//x"]


def test_resolve_element_asset_branches():
    case = types.SimpleNamespace(module_id=22, id=7, config={})

    class _DB:
        def __init__(self, asset=None, module=None):
            self.asset = asset
            self.module = module

        async def get(self, model, pk):
            if model is wlc.WebElementAsset:
                return self.asset
            if model is wlc.Module:
                return self.module
            return None

    params = {"selector": "#x"}
    resolved, asset, err = asyncio.run(wlc._resolve_element_asset(_DB(), case, params))
    assert resolved is params and asset is None and err is None

    _r, _a, err = asyncio.run(wlc._resolve_element_asset(_DB(), case, {"element_asset_id": "abc"}))
    assert err == "元素资产 ID 无效"

    _r, _a, err = asyncio.run(wlc._resolve_element_asset(_DB(), case, {"element_asset_id": 1}))
    assert err == "元素资产不存在"

    module = types.SimpleNamespace(project_id=5)
    asset = types.SimpleNamespace(project_id=99, locator={"strategy": "css", "value": "#a"}, fallback_locators=[])
    _r, _a, err = asyncio.run(
        wlc._resolve_element_asset(_DB(asset=asset, module=module), case, {"element_asset_id": 1})
    )
    assert err == "元素资产不属于当前项目"

    asset = types.SimpleNamespace(project_id=5, locator={"strategy": "css", "value": ""}, fallback_locators=[])
    _r, asset_out, err = asyncio.run(
        wlc._resolve_element_asset(_DB(asset=asset, module=module), case, {"element_asset_id": 1})
    )
    assert err == "元素资产没有可用定位器" and asset_out is asset

    asset = types.SimpleNamespace(
        project_id=5,
        locator={"strategy": "css", "value": "#a"},
        fallback_locators=[{"strategy": "css", "value": "#b"}],
    )
    resolved, asset_out, err = asyncio.run(
        wlc._resolve_element_asset(_DB(asset=asset, module=module), case, {"element_asset_id": "1"})
    )
    assert err is None
    assert resolved["selector"] == "#a"
    assert resolved["_asset_selectors"] == ["#a", "#b"]
    assert resolved["element_asset_id"] == "1"


def test_mark_element_asset_failed_branches():
    class _DB:
        def __init__(self):
            self.commits = 0

        async def commit(self):
            self.commits += 1

    asset = types.SimpleNamespace()
    db = _DB()
    asyncio.run(wlc._mark_element_asset_failed(db, asset, "x" * 3000))
    assert db.commits == 1
    assert len(asset.last_failure_reason) == 2000
    assert asset.last_failed_at is not None

    asyncio.run(wlc._mark_element_asset_failed(db, None, "boom"))
    asyncio.run(wlc._mark_element_asset_failed(db, asset, None))
    assert db.commits == 1


def test_execute_step_text_and_visibility_assertions():
    page = _FakePage(body_text="欢迎来到首页")
    page.locator_behavior["text=登录"] = TimeoutError("no text locator")
    assert asyncio.run(wlc._execute_step(page, "assert_text", {"text": "首页"}, 500)) == {"success": True}

    page2 = _FakePage(body_text="其它内容")
    page2.locator_behavior["text=登录"] = TimeoutError("no text locator")
    result = asyncio.run(wlc._execute_step(page2, "assert_text", {"text": "登录"}, 500))
    assert result["success"] is False and "未找到文本" in result["error"]

    page3 = _FakePage()
    page3.locator_behavior["#gone"] = False
    result = asyncio.run(wlc._execute_step(page3, "assert_visible", {"selector": "#gone"}, 500))
    assert result["success"] is False and result["error"] == "元素不可见: #gone"
    assert asyncio.run(wlc._execute_step(page3, "assert_visible", {"selector": "#ok"}, 500))["success"] is True


def test_execute_step_visual_assert_branches(monkeypatch):
    page = _FakePage()
    page.locator_text["#t"] = "欢迎 OK"
    assert asyncio.run(
        wlc._execute_step(page, "assert_visual_element", {"selector": "#t", "expected_text": "OK"}, 500)
    ) == {"success": True}

    result = asyncio.run(
        wlc._execute_step(page, "assert_visual_element", {"selector": "#t", "expected_text": "缺失"}, 500)
    )
    assert result["success"] is False and "未匹配到预期文本" in result["error"]

    page.locator_behavior["#boom"] = RuntimeError("locator exploded")
    result = asyncio.run(
        wlc._execute_step(page, "assert_visual_element", {"selector": "#boom", "expected_text": "x"}, 500)
    )
    assert result["success"] is False and "视觉元素定位异常" in result["error"]

    captured = {}

    def _fake_eval(target, template, threshold=0.85):
        captured["args"] = (target, template, threshold)
        return (True, 0.99, None)

    monkeypatch.setattr("app.services.visual_assertion.evaluate_visual_assertion", _fake_eval)
    result = asyncio.run(
        wlc._execute_step(page, "assert_visual_element", {"selector": "#t", "image_template": {"a": 1}}, 500)
    )
    assert result["success"] is True
    assert result["data"]["similarity"] == 0.99
    assert captured["args"] == (page.screenshot_bytes, {"a": 1}, 0.85)

    monkeypatch.setattr(
        "app.services.visual_assertion.evaluate_visual_assertion", lambda *a, **kw: (False, 0.2, "差异过大")
    )
    result = asyncio.run(wlc._execute_step(page, "assert_visual_element", {"image_template": {"a": 1}}, 500))
    assert result["success"] is False and result["error"] == "差异过大"

    def _boom(*_args, **_kwargs):
        raise ValueError("compare failed")

    monkeypatch.setattr("app.services.visual_assertion.evaluate_visual_assertion", _boom)
    result = asyncio.run(wlc._execute_step(page, "assert_visual_element", {"image_template": {"a": 1}}, 500))
    assert result["success"] is False and "视觉截图与比对异常" in result["error"]


def test_execute_step_save_storage_state_branches(monkeypatch):
    uploads = []
    monkeypatch.setattr(wlc, "upload_bytes", lambda name, data, ct: uploads.append((name, data, ct)))
    page = _FakePage()
    context = _FakeBrowserContext(page=page, storage_state_value={"cookies": []})
    page.context = context

    assert asyncio.run(wlc._execute_step(page, "save_storage_state", {}, 100)) == {"success": True}
    assert uploads == []

    result = asyncio.run(wlc._execute_step(page, "save_storage_state", {"name": "login", "_project_id": 5}, 100))
    assert result["success"] is True
    assert result["data"]["saved_name"] == "login"
    assert uploads[0][0] == "storage-states/projects/5/login.json"

    context.storage_state_error = RuntimeError("state boom")
    result = asyncio.run(wlc._execute_step(page, "save_storage_state", {"_project_id": 5}, 100))
    assert result["success"] is False and "保存登录态失败" in result["error"]


def test_execute_step_misc_actions():
    page = _FakePage()
    assert asyncio.run(wlc._execute_step(page, "select", {"selector": "#s", "value": "v"}, 100))["success"] is True
    assert page.selects == [("#s", "v")]
    assert asyncio.run(wlc._execute_step(page, "press", {"key": "Enter"}, 100))["success"] is True
    assert page.keyboard_presses == ["Enter"]
    assert asyncio.run(wlc._execute_step(page, "press", {"selector": "#i", "key": "Tab"}, 100))["success"] is True
    assert page.presses == [("#i", "Tab")]
    assert asyncio.run(wlc._execute_step(page, "hover", {"selector": "#h"}, 100))["success"] is True
    assert page.hovers == ["#h"]
    assert asyncio.run(wlc._execute_step(page, "wait", {"ms": 1}, 100))["success"] is True
    assert asyncio.run(wlc._execute_step(page, "screenshot", {}, 100))["data"] == {"manual_screenshot": True}
    result = asyncio.run(wlc._execute_step(page, "rotate", {}, 100))
    assert result["success"] is False and "未知操作类型" in result["error"]


def test_execute_step_with_asset_fallback_retries_selectors():
    page = _FakePage()
    result = asyncio.run(wlc._execute_step_with_asset_fallback(page, "click", {"selector": "#a"}, 100))
    assert result == {"success": True} and page.clicks == ["#a"]

    page2 = _FakePage()
    page2.locator_behavior["#a"] = RuntimeError("first broken")
    params = {"selector": "#a", "_asset_selectors": ["#a", "#b"]}
    result = asyncio.run(wlc._execute_step_with_asset_fallback(page2, "click", params, 100))
    assert result["success"] is True
    assert result["data"]["fallback_locator_index"] == 1
    assert page2.clicks == ["#b"]

    page3 = _FakePage()
    page3.locator_behavior["#a"] = RuntimeError("broken a")
    page3.locator_behavior["#b"] = RuntimeError("broken b")
    result = asyncio.run(wlc._execute_step_with_asset_fallback(page3, "click", params, 100))
    assert result["success"] is False and result["error"] == "broken a"


def test_execute_web_file_step_upload_paths(monkeypatch):
    page = _FakePage()
    monkeypatch.setattr(wlc, "download_file", lambda name, path: Path(path).write_bytes(b"uploaded-bytes"))

    result = asyncio.run(wlc._execute_web_file_step(page, "upload", {}, 100, 5, 99))
    assert result["success"] is False and result["error"] == "文件步骤缺少选择器"

    result = asyncio.run(
        wlc._execute_web_file_step(page, "upload", {"selector": "#f", "object_name": "other/x"}, 100, None, 99)
    )
    assert result["success"] is False and result["error"] == "上传文件引用必须属于当前项目"

    result = asyncio.run(
        wlc._execute_web_file_step(
            page, "upload", {"selector": "#f", "object_name": "web-files/projects/5/a.txt"}, 100, 5, 99
        )
    )
    assert result["success"] is True and result["data"]["object_name"] == "web-files/projects/5/a.txt"
    assert page.uploaded_files and page.uploaded_files[0][0] == "#f"
    assert not Path(page.uploaded_files[0][1]).exists()

    def _boom(name, path):
        raise RuntimeError("minio down")

    monkeypatch.setattr(wlc, "download_file", _boom)
    result = asyncio.run(
        wlc._execute_web_file_step(
            page, "upload", {"selector": "#f", "object_name": "web-files/projects/5/a.txt"}, 100, 5, 99
        )
    )
    assert result["success"] is False and result["error"] == "minio down"

    result = asyncio.run(wlc._execute_web_file_step(page, "move", {"selector": "#f"}, 100, 5, 99))
    assert result["success"] is False and result["error"] == "未知文件操作类型: move"


def test_execute_web_file_step_download_paths(monkeypatch):
    uploaded = []
    monkeypatch.setattr(wlc, "upload_file", lambda name, path, ct: uploaded.append((name, Path(path), ct)))

    local = Path(tempfile.NamedTemporaryFile(prefix="atp-dl-", delete=False).name)
    local.write_bytes(b"payload")
    download = _FakeDownload(local, suggested_filename="my report.csv")

    page = _FakePage()
    page.expect_download_cm = _ExpectDownloadCM(download)
    result = asyncio.run(wlc._execute_web_file_step(page, "download", {"selector": "#dl"}, 100, 5, 99))
    assert result["success"] is True
    assert result["data"]["object_name"].startswith("web-files/runs/99/")
    assert result["data"]["object_name"].endswith("_my_report.csv")
    assert result["data"]["filename"] == "my_report.csv"
    assert uploaded[0][1] == local

    page2 = _FakePage()
    page2.expect_download_cm = _ExpectDownloadCM(download)
    page2.locator_behavior["#dl"] = RuntimeError("click boom")
    result = asyncio.run(wlc._execute_web_file_step(page2, "download", {"selector": "#dl"}, 100, 5, 99))
    assert result["success"] is False and result["error"] == "click boom"

    page3 = _FakePage()
    page3.expect_download_cm = _ExpectDownloadCM(_FakeDownload(None))
    result = asyncio.run(wlc._execute_web_file_step(page3, "download", {"selector": "#dl"}, 100, 5, 99))
    assert result["success"] is False and result["error"] == "下载未生成本地文件"

    page4 = _FakePage(support_download=False)
    result = asyncio.run(wlc._execute_web_file_step(page4, "download", {"selector": "#dl"}, 100, 5, 99))
    assert result["success"] is False and result["error"] == "当前浏览器页面不支持下载事件监听"

    local.unlink(missing_ok=True)


def test_execute_visual_assert_branches(monkeypatch):
    page = _FakePage(screenshot_bytes=b"CURRENT")

    class _DB:
        def __init__(self, baseline):
            self.baseline = baseline

        async def get(self, model, pk):
            return self.baseline

    result = asyncio.run(wlc._execute_visual_assert(_DB(None), page, {"baseline_id": "abc"}, 5, 99, 0))
    assert result["success"] is False and result["error"] == "视觉断言缺少有效基线 ID"

    result = asyncio.run(wlc._execute_visual_assert(_DB(None), page, {"baseline_id": 1}, 5, 99, 0))
    assert result["success"] is False and result["error"] == "视觉基线不存在"

    baseline = types.SimpleNamespace(
        project_id=99, object_name="b.png", threshold=0.9, pixel_threshold=10, ignore_regions=[]
    )
    result = asyncio.run(wlc._execute_visual_assert(_DB(baseline), page, {"baseline_id": 1}, 5, 99, 0))
    assert result["success"] is False and result["error"] == "视觉基线不属于当前项目"

    baseline = types.SimpleNamespace(
        project_id=5, object_name="b.png", threshold=0.9, pixel_threshold=10, ignore_regions=[]
    )
    monkeypatch.setattr(wlc, "read_bytes", lambda name: b"BASELINE")
    captured = {}

    def _compare(baseline_bytes, current_bytes, **kwargs):
        captured["args"] = (baseline_bytes, current_bytes, kwargs)
        return {"match": False, "diff_png": b"DIFF", "similarity": 0.1}

    uploads = []
    monkeypatch.setattr(wlc, "compare_png_bytes", _compare)
    monkeypatch.setattr(wlc, "upload_bytes", lambda name, data, ct: uploads.append((name, data, ct)))
    monkeypatch.setattr(wlc, "presigned_url", lambda name, expires_seconds=None: f"https://minio/{name}")

    result = asyncio.run(wlc._execute_visual_assert(_DB(baseline), page, {"baseline_id": 1}, 5, 99, 3))
    assert result["success"] is False and result["error"] == "视觉差异超过阈值"
    assert result["data"]["diff_url"] == "https://minio/visual-diffs/runs/99/step_3.png"
    assert uploads[0] == ("visual-diffs/runs/99/step_3.png", b"DIFF", "image/png")
    assert captured["args"] == (
        b"BASELINE",
        b"CURRENT",
        {"threshold": 0.9, "pixel_threshold": 10, "ignore_regions": []},
    )
    assert "diff_png" not in result["data"]

    monkeypatch.setattr(wlc, "compare_png_bytes", lambda *a, **kw: {"match": True, "similarity": 0.99})
    result = asyncio.run(wlc._execute_visual_assert(_DB(baseline), page, {"baseline_id": 1}, 5, 99, 4))
    assert result["success"] is True and result["error"] is None

    def _raise_compare(*_args, **_kwargs):
        raise wlc.VisualCompareError("阈值配置错误")

    monkeypatch.setattr(wlc, "compare_png_bytes", _raise_compare)
    result = asyncio.run(wlc._execute_visual_assert(_DB(baseline), page, {"baseline_id": 1}, 5, 99, 5))
    assert result["success"] is False and result["error"] == "阈值配置错误"

    def _read_boom(name):
        raise OSError("read failed")

    monkeypatch.setattr(wlc, "read_bytes", _read_boom)
    result = asyncio.run(wlc._execute_visual_assert(_DB(baseline), page, {"baseline_id": 1}, 5, 99, 6))
    assert result["success"] is False and result["error"] == "read failed"


def test_expand_page_object_steps_branches():
    class _DB:
        def __init__(self, page_object=None):
            self.page_object = page_object

        async def get(self, model, pk):
            return self.page_object

    plain = {"action": "click", "params": {"selector": "#a"}}
    expanded, err = asyncio.run(wlc._expand_page_object_steps(_DB(), [plain], 5))
    assert expanded == [plain] and err is None

    step = {"action": "page_object", "name": "登录页", "params": "nope"}
    expanded, err = asyncio.run(wlc._expand_page_object_steps(_DB(), [step], 5))
    assert expanded == [] and err == "页面对象步骤缺少有效页面对象 ID"

    expanded, err = asyncio.run(
        wlc._expand_page_object_steps(_DB(), [{"action": "page_object", "params": {"page_object_id": "abc"}}], 5)
    )
    assert err == "页面对象步骤缺少有效页面对象 ID"

    expanded, err = asyncio.run(
        wlc._expand_page_object_steps(_DB(None), [{"action": "page_object", "params": {"page_object_id": 1}}], 5)
    )
    assert err == "页面对象不存在"

    po = types.SimpleNamespace(project_id=99, element_refs=[], actions=[{"step": "click"}])
    expanded, err = asyncio.run(
        wlc._expand_page_object_steps(_DB(po), [{"action": "page_object", "params": {"page_object_id": 1}}], 5)
    )
    assert err == "页面对象不属于当前项目"

    po = types.SimpleNamespace(project_id=5, element_refs=[], actions=[])
    expanded, err = asyncio.run(
        wlc._expand_page_object_steps(_DB(po), [{"action": "page_object", "params": {"page_object_id": 1}}], 5)
    )
    assert err == "页面对象未配置公共动作"

    po = types.SimpleNamespace(
        project_id=5,
        element_refs=[{"alias": "btn", "asset_id": 9}],
        actions=[
            "not-a-dict",
            {"step": "click", "name": "点击按钮", "alias": "btn"},
            {"step": "input", "element": "btn", "params": {"text": "{{U}}"}},
        ],
    )
    expanded, err = asyncio.run(
        wlc._expand_page_object_steps(
            _DB(po), [{"action": "page_object", "name": "登录页", "params": {"page_object_id": 1}}], 5
        )
    )
    assert err is None
    assert [item["action"] for item in expanded] == ["click", "input"]
    assert expanded[0]["name"] == "登录页 / 点击按钮"
    assert expanded[0]["params"]["element_asset_id"] == 9
    assert expanded[1]["name"] == "登录页 / 动作_3"
    assert expanded[1]["params"]["element_asset_id"] == 9

    po_bad = types.SimpleNamespace(project_id=5, element_refs=[], actions=[{"step": "page_object"}])
    expanded, err = asyncio.run(
        wlc._expand_page_object_steps(_DB(po_bad), [{"action": "page_object", "params": {"page_object_id": 1}}], 5)
    )
    assert err == "页面对象包含无效公共动作"

    expanded, err = asyncio.run(
        wlc._expand_page_object_steps(
            _DB(types.SimpleNamespace(project_id=5, element_refs=[], actions=[{"step": "click"}])),
            [{"action": "page_object", "params": {"page_object_id": 1}}],
            None,
        )
    )
    assert err == "页面对象不属于当前项目"


def test_run_web_matrix_aggregates_variants(monkeypatch):
    events, _page, _ctx = _install_web_env(monkeypatch)

    async def _variant(**kwargs):
        return {
            "run_id": kwargs["child_id"],
            "index": kwargs["index"],
            "label": kwargs["variant"].get("label"),
            "browser": kwargs["variant"].get("browser"),
            "viewport": kwargs["variant"].get("viewport"),
            "status": "passed" if kwargs["index"] == 0 else "failed",
            "duration_ms": 10,
        }

    monkeypatch.setattr(wlc, "_run_web_matrix_variant", _variant)
    db, parent, case = _run_entities([])
    matrix = [{"label": "a", "browser": "chromium"}, {"label": "b", "browser": "firefox"}]
    asyncio.run(wlc._run_web_matrix(db, parent, case, {}, matrix))

    assert parent.result_summary["matrix_total"] == 2
    assert parent.result_summary["matrix_passed"] == 1
    assert parent.result_summary["matrix_failed"] == 1
    assert parent.result_summary["matrix_error"] == 0
    assert [item["status"] for item in parent.result_summary["matrix_variants"]] == ["passed", "failed"]
    assert parent.status == RunStatus.failed
    assert [getattr(item, "iteration_index", None) for item in db.added] == [0, 1]
    assert events.published[-1]["status"] == "failed"
    assert len(events.published[-1]["matrix"]) == 2


def test_run_web_matrix_variant_paths(monkeypatch):
    import app.core.database as app_db

    def _session_cm(session):
        class _CM:
            async def __aenter__(self):
                return session

            async def __aexit__(self, *exc):
                return False

        return _CM()

    class _Session:
        def __init__(self, child):
            self.child = child
            self.commits = 0

        async def get(self, model, pk):
            return self.child

        async def commit(self):
            self.commits += 1

    monkeypatch.setattr(app_db, "AsyncSessionLocal", lambda: _session_cm(_Session(None)), raising=False)
    out = asyncio.run(
        wlc._run_web_matrix_variant(
            child_id=1, case_id=2, module_id=3, base_config={}, extra_vars={}, index=0, variant={"label": "a"}
        )
    )
    assert out["status"] == "error" and out["error"] == "矩阵子运行不存在"
    assert out["run_id"] == 1 and out["index"] == 0

    child = types.SimpleNamespace(id=501, status=RunStatus.pending, duration_ms=None, error_message=None)
    session = _Session(child)
    monkeypatch.setattr(app_db, "AsyncSessionLocal", lambda: _session_cm(session), raising=False)
    captured = {}

    async def _run(child_db, child_run, case_variant, extra_vars):
        captured["config"] = case_variant.config
        child_run.status = RunStatus.passed
        child_run.duration_ms = 12

    monkeypatch.setattr(wlc, "run_web_lowcode", _run)
    out = asyncio.run(
        wlc._run_web_matrix_variant(
            child_id=501,
            case_id=2,
            module_id=3,
            base_config={"browser_matrix": [1], "steps": []},
            extra_vars={"A": 1},
            index=1,
            variant={"label": "b", "browser": "firefox"},
        )
    )
    assert out["status"] == "passed" and out["duration_ms"] == 12
    assert out["label"] == "b" and out["browser"] == "firefox"
    assert captured["config"]["browser"] == "firefox"
    assert captured["config"]["_web_matrix_variant"] is True
    assert "browser_matrix" not in captured["config"]
    assert session.commits == 1

    def _boom(*_args, **_kwargs):
        raise RuntimeError("variant boom")

    monkeypatch.setattr(wlc, "run_web_lowcode", _boom)
    child2 = types.SimpleNamespace(id=502, status=RunStatus.pending, duration_ms=None, error_message=None)
    session2 = _Session(child2)
    monkeypatch.setattr(app_db, "AsyncSessionLocal", lambda: _session_cm(session2), raising=False)
    out = asyncio.run(
        wlc._run_web_matrix_variant(
            child_id=502, case_id=2, module_id=3, base_config={}, extra_vars={}, index=2, variant={"label": "c"}
        )
    )
    assert out["status"] == "error" and child2.error_message == "variant boom"
    assert session2.commits == 2


def test_run_web_lowcode_matrix_build_error(monkeypatch):
    events, _page, _ctx = _install_web_env(monkeypatch)

    def _boom(cfg):
        raise wlc.WebMatrixError("矩阵配置无效")

    monkeypatch.setattr(wlc, "build_web_matrix", _boom)
    db, run, case = _run_entities([{"action": "goto", "params": {"url": "https://a"}}])
    asyncio.run(wlc.run_web_lowcode(db, run, case, {}))
    assert run.status == RunStatus.error
    assert run.error_message == "矩阵配置无效"
    assert events.published[-1] == {"type": "completed", "run_id": run.id, "status": "error"}


def test_run_web_lowcode_delegates_to_matrix(monkeypatch):
    events, _page, _ctx = _install_web_env(monkeypatch)
    monkeypatch.setattr(wlc, "build_web_matrix", lambda cfg: [{"browser": "chromium"}, {"browser": "firefox"}])
    calls = []

    async def _matrix(db_arg, run_arg, case_arg, extra_vars, matrix):
        calls.append(matrix)

    monkeypatch.setattr(wlc, "_run_web_matrix", _matrix)
    db, run, case = _run_entities([{"action": "goto", "params": {}}])
    asyncio.run(wlc.run_web_lowcode(db, run, case, {}))
    assert calls and len(calls[0]) == 2
    assert events.acquire_kwargs is None


def test_run_web_lowcode_rejects_empty_steps_and_unknown_browser(monkeypatch):
    events, _page, _ctx = _install_web_env(monkeypatch)
    db, run, case = _run_entities([])
    asyncio.run(wlc.run_web_lowcode(db, run, case, {}))
    assert run.status == RunStatus.error and run.error_message == "低代码用例未配置任何步骤"
    assert events.published[-1]["status"] == "error"

    events2, _p2, _c2 = _install_web_env(monkeypatch)
    db2, run2, case2 = _run_entities([{"action": "goto", "params": {}}], cfg={"browser": "edge"})
    asyncio.run(wlc.run_web_lowcode(db2, run2, case2, {}))
    assert run2.status == RunStatus.error and "不支持的浏览器: edge" in run2.error_message
    assert events2.acquire_kwargs is None


def test_run_web_lowcode_page_object_expansion_error(monkeypatch):
    events, _page, _ctx = _install_web_env(monkeypatch)
    db, run, case = _run_entities([{"action": "page_object", "params": {"page_object_id": "oops"}}])
    asyncio.run(wlc.run_web_lowcode(db, run, case, {}))
    assert run.status == RunStatus.error
    assert run.error_message == "页面对象步骤缺少有效页面对象 ID"
    assert events.published[-1]["status"] == "error"
    assert db.commits >= 1


def test_run_web_lowcode_loads_storage_state(monkeypatch):
    events, _page, _ctx = _install_web_env(monkeypatch)
    monkeypatch.setattr(wlc, "read_bytes", lambda name: b'{"cookies": [1]}')
    db, run, case = _run_entities([{"action": "goto", "params": {"url": "https://a"}}], cfg={"use_storage_state": True})
    asyncio.run(wlc.run_web_lowcode(db, run, case, {}))
    assert run.status == RunStatus.passed
    assert events.acquire_kwargs["context_options"]["storage_state"] == {"cookies": [1]}

    calls = []

    def _boom(name):
        calls.append(name)
        raise RuntimeError("minio down")

    events2, _p2, _c2 = _install_web_env(monkeypatch)
    monkeypatch.setattr(wlc, "read_bytes", _boom)
    db2, run2, case2 = _run_entities(
        [{"action": "goto", "params": {"url": "https://a"}}], cfg={"use_storage_state": "login"}
    )
    asyncio.run(wlc.run_web_lowcode(db2, run2, case2, {}))
    assert calls == ["storage-states/projects/5/login.json"]
    assert "storage_state" not in events2.acquire_kwargs["context_options"]
    assert run2.status == RunStatus.passed


def test_run_web_lowcode_full_success_uploads_artifacts(monkeypatch):
    tracing = _FakeTracing(write_on_stop=True)
    page = _FakePage(body_text="hello")
    events, page, context = _install_web_env(monkeypatch, page=page, tracing=tracing, write_video=True)
    steps = [
        {"action": "goto", "name": "打开", "params": {"url": "https://demo"}},
        {"action": "click", "params": {"selector": "#login"}},
    ]
    cfg = {
        "save_storage_state": "default",
        "locale": "zh-CN",
        "user_agent": "ATP/1.0",
        "device_scale_factor": 2,
        "viewport": {"width": 800, "height": 600},
    }
    db, run, case = _run_entities(steps, cfg=cfg)
    asyncio.run(wlc.run_web_lowcode(db, run, case, {"WHO": "world"}))

    assert run.status == RunStatus.passed
    assert len(db.added) == 2
    assert db.added[0].screenshot_url == "https://minio/screenshots/runs/99/step_0.png"
    assert page.gotos == ["https://demo"]

    options = events.acquire_kwargs["context_options"]
    assert options["locale"] == "zh-CN"
    assert options["user_agent"] == "ATP/1.0"
    assert options["device_scale_factor"] == 2.0
    assert options["viewport"] == {"width": 800, "height": 600}
    assert tracing.start_kwargs == {"screenshots": True, "snapshots": True, "sources": False}

    summary = run.result_summary
    assert summary["video_url"] == "https://minio/videos/runs/99/recording.webm"
    assert summary["trace_url"] == "https://minio/traces/runs/99/trace.zip"
    assert summary["blocked_requests"] == []
    assert summary["network_events"] == []
    assert summary["console_events"] == []

    uploaded_names = [name for name, _data, _ct in events.uploaded]
    assert "storage-states/projects/5/default.json" in uploaded_names
    assert "screenshots/runs/99/step_0.png" in uploaded_names
    file_names = [name for name, _path, _ct in events.upload_files]
    assert "videos/runs/99/recording.webm" in file_names
    assert "traces/runs/99/trace.zip" in file_names
    assert len(events.released) == 1
    assert events.reset_runs == [99]
    assert events.cleared == [99]
    completed = events.published[-1]
    assert completed["type"] == "completed" and completed["status"] == "passed"
    assert completed["video_url"] == summary["video_url"]


def test_run_web_lowcode_trace_upload_failure(monkeypatch):
    tracing = _FakeTracing(write_on_stop=True)
    events, _page, _ctx = _install_web_env(monkeypatch, tracing=tracing)

    def _upload_file(name, path, content_type):
        events.upload_files.append((name, str(path), content_type))
        if name.startswith("traces/"):
            raise RuntimeError("trace upload boom")

    monkeypatch.setattr(wlc, "upload_file", _upload_file)
    db, run, case = _run_entities([{"action": "click", "params": {"selector": "#a"}}])
    asyncio.run(wlc.run_web_lowcode(db, run, case, {}))
    assert run.status == RunStatus.passed
    assert "trace_url" not in run.result_summary
    assert any(name.startswith("traces/") for name, _p, _c in events.upload_files)


def test_run_web_lowcode_heals_locator_failure(monkeypatch):
    events, _page, _ctx = _install_web_env(monkeypatch)
    monkeypatch.setattr(wlc, "is_locator_failure", lambda message: True)

    async def _failing_step(*args, **kwargs):
        return {"success": False, "error": "locator timeout"}

    monkeypatch.setattr(wlc, "_execute_step", _failing_step)
    db, run, case = _run_entities([{"action": "click", "params": {"selector": "#flaky"}}])
    asyncio.run(wlc.run_web_lowcode(db, run, case, {}))
    assert run.status == RunStatus.passed
    assert getattr(events, "healed", False) is True
    assert db.added[0].status == RunStatus.passed


def test_run_web_lowcode_step_failure_without_connected_flag(monkeypatch):
    browser = types.SimpleNamespace(connected=True)
    events, _page, _ctx = _install_web_env(monkeypatch, browser=browser)

    async def _failing_step(*args, **kwargs):
        return {"success": False, "error": "click exploded"}

    monkeypatch.setattr(wlc, "_execute_step", _failing_step)
    db, run, case = _run_entities(
        [
            {"action": "click", "params": {"selector": "#bad"}},
            {"action": "click", "params": {"selector": "#next"}},
        ]
    )
    asyncio.run(wlc.run_web_lowcode(db, run, case, {}))
    assert run.status == RunStatus.failed
    assert len(db.added) == 1
    assert db.added[0].error_message == "click exploded"
    assert events.published[-1]["status"] == "failed"


def test_run_web_lowcode_storage_state_save_failure(monkeypatch):
    events, _page, _ctx = _install_web_env(monkeypatch, storage_state_error=RuntimeError("state broken"))
    db, run, case = _run_entities([{"action": "click", "params": {"selector": "#a"}}], cfg={"save_storage_state": True})
    asyncio.run(wlc.run_web_lowcode(db, run, case, {}))
    assert run.status == RunStatus.passed
    assert not any(name.startswith("storage-states/") for name, _d, _c in events.uploaded)


def test_run_web_lowcode_records_asset_resolution_error(monkeypatch):
    events, _page, _ctx = _install_web_env(monkeypatch)

    async def _resolve(db_arg, case_arg, params):
        return params, None, "元素资产 ID 无效"

    monkeypatch.setattr(wlc, "_resolve_element_asset", _resolve)
    db, run, case = _run_entities([{"action": "click", "params": {"element_asset_id": "x"}}])
    asyncio.run(wlc.run_web_lowcode(db, run, case, {}))
    assert run.status == RunStatus.failed
    assert db.added[0].error_message == "元素资产 ID 无效"


def test_run_web_lowcode_dispatches_file_and_visual_actions(monkeypatch):
    events, _page, _ctx = _install_web_env(monkeypatch)
    calls = []

    async def _file(page, action, params, timeout_ms, project_id, run_id):
        calls.append(("file", action, project_id, params.get("_project_id")))
        return {"success": True, "data": {"object_name": "web-files/runs/99/x"}}

    async def _visual(db_arg, page, params, project_id, run_id, step_index):
        calls.append(("visual", project_id, step_index, params.get("_project_id")))
        return {"success": True, "data": {"similarity": 0.99}}

    monkeypatch.setattr(wlc, "_execute_web_file_step", _file)
    monkeypatch.setattr(wlc, "_execute_visual_assert", _visual)
    steps = [
        {"action": "upload", "params": {"selector": "#f"}},
        {"action": "visual_assert", "params": {"baseline_id": 1}},
    ]
    db, run, case = _run_entities(steps)
    asyncio.run(wlc.run_web_lowcode(db, run, case, {}))
    assert run.status == RunStatus.passed
    assert calls == [("file", "upload", 5, 5), ("visual", 5, 1, 5)]
    assert db.added[0].response_data == {"object_name": "web-files/runs/99/x"}


def test_run_web_lowcode_blocks_risky_requests(monkeypatch):
    events, _page, _ctx = _install_web_env(monkeypatch)

    async def _guard(route, blocked):
        blocked.append({"url": "https://ads.example/x.js", "reason": "blocked"})
        return False

    monkeypatch.setattr(wlc, "guard_browser_request", _guard)
    db, run, case = _run_entities([{"action": "goto", "params": {"url": "https://demo"}}])
    asyncio.run(wlc.run_web_lowcode(db, run, case, {}))
    assert run.error_message == "浏览器请求被网络安全策略阻止"
    assert run.result_summary["blocked_requests"] == [{"url": "https://ads.example/x.js", "reason": "blocked"}]


def test_run_web_lowcode_finally_failures_do_not_break_run(monkeypatch):
    tracing = _FakeTracing(write_on_stop=True, stop_error=RuntimeError("stop boom"))
    events, _page, _ctx = _install_web_env(monkeypatch, tracing=tracing, write_video=True)

    class _FlushBoom:
        def __init__(self, db_arg):
            self.db = db_arg

        async def add(self, item):
            self.db.add(item)

        async def flush(self):
            raise RuntimeError("flush boom")

    monkeypatch.setattr(wlc, "StepResultBatchCollector", _FlushBoom)

    def _upload_file(name, path, content_type):
        events.upload_files.append((name, str(path), content_type))
        raise RuntimeError("upload boom")

    monkeypatch.setattr(wlc, "upload_file", _upload_file)
    db, run, case = _run_entities([{"action": "click", "params": {"selector": "#a"}}])
    asyncio.run(wlc.run_web_lowcode(db, run, case, {}))
    assert run.status == RunStatus.passed
    assert "video_url" not in run.result_summary
    assert "trace_url" not in run.result_summary
    assert len(events.released) == 1
    assert events.published[-1]["status"] == "passed"


def test_run_web_lowcode_handles_cancelled_run(monkeypatch):
    events, _page, _ctx = _install_web_env(monkeypatch)

    async def _cancelled(*args, **kwargs):
        for arg in args:
            if asyncio.iscoroutine(arg):
                arg.close()
        raise wlc.WebRunCancelled("运行已请求取消")

    monkeypatch.setattr(wlc, "_await_with_cancel", _cancelled)
    db, run, case = _run_entities([{"action": "goto", "params": {"url": "https://demo"}}])
    asyncio.run(wlc.run_web_lowcode(db, run, case, {}))
    assert run.status == RunStatus.cancelled
    assert events.published[-1]["status"] == "cancelled"
    assert len(events.released) == 1
    assert events.reset_runs == [99]


def test_sanitize_and_replace_helpers(monkeypatch):
    monkeypatch.setattr(wlc, "sanitize_network_url", lambda url: "SAN")
    assert wlc._sanitize_network_url("https://a.com?t=1") == "SAN"
    assert wlc._replace_vars("", {"A": "1"}) == ""
    assert wlc._replace_vars("{{A}}-{{B}}", {"A": "1"}) == "1-{{B}}"
    assert wlc._replace_vars_in_params({"a": "{{A}}", "b": {"c": "{{A}}"}, "d": 3}, {"A": "9"}) == {
        "a": "9",
        "b": {"c": "9"},
        "d": 3,
    }


def test_await_with_cancel_cancellation_and_exceptions(monkeypatch):
    monkeypatch.setattr(wlc, "is_cancel_requested", lambda run_id: True)

    async def _pending():
        await asyncio.Event().wait()

    async def run_cancelled():
        try:
            await wlc._await_with_cancel(1, _pending(), None)
        except wlc.WebRunCancelled as exc:
            return str(exc)
        raise AssertionError("expected WebRunCancelled")

    assert "用户取消执行" in asyncio.run(run_cancelled())

    class _BrokenBrowser:
        def is_connected(self):
            raise ZeroDivisionError("connection check exploded")

    async def run_broken():
        try:
            await wlc._await_with_cancel(1, _pending(), _BrokenBrowser())
        except ZeroDivisionError as exc:
            return str(exc)
        raise AssertionError("expected ZeroDivisionError")

    assert "connection check exploded" in asyncio.run(run_broken())


def test_await_with_cancel_completes_after_polling(monkeypatch):
    monkeypatch.setattr(wlc, "is_cancel_requested", lambda run_id: False)

    async def _slow():
        await asyncio.sleep(0.3)
        return "完成"

    assert asyncio.run(wlc._await_with_cancel(1, _slow(), None)) == "完成"


def test_await_with_cancel_exits_when_task_finishes_between_polls(monkeypatch):
    def _cancel_check(run_id):
        import time

        time.sleep(0.05)
        return False

    monkeypatch.setattr(wlc, "is_cancel_requested", _cancel_check)

    async def run():
        ready = asyncio.Event()

        class _Browser:
            def is_connected(self):
                ready.set()
                return True

        async def _waits_for_signal():
            await ready.wait()
            return "done"

        return await wlc._await_with_cancel(1, _waits_for_signal(), _Browser())

    assert asyncio.run(run()) == "done"


def test_await_with_cancel_loop_exit_without_break(monkeypatch):
    monkeypatch.setattr(wlc, "is_cancel_requested", lambda run_id: False)
    calls = {"n": 0}

    async def _fake_wait(fs, timeout=None):
        calls["n"] += 1
        if calls["n"] >= 2:
            for future in fs:
                if not future.done():
                    await future
        return set(), set(fs)

    monkeypatch.setattr(asyncio, "wait", _fake_wait)

    async def run():
        async def _slow():
            await asyncio.sleep(0.05)
            return "done"

        return await wlc._await_with_cancel(1, _slow(), None)

    assert asyncio.run(run()) == "done"


def test_safe_publish_swallows_errors(monkeypatch):
    async def _boom(run_id, payload):
        raise RuntimeError("redis down")

    monkeypatch.setattr(wlc, "publish_run_event", _boom)
    asyncio.run(wlc._safe_publish(1, {"type": "x"}))


def test_take_screenshot_handles_failure():
    class _Page:
        async def screenshot(self, type="png"):
            raise RuntimeError("no screenshot")

    assert asyncio.run(wlc._take_screenshot(_Page(), 5, 0)) is None


def test_execute_step_fill_and_assert_text_fallback():
    class _Page:
        def __init__(self):
            self.fills = []

        async def fill(self, selector, value, timeout=None):
            self.fills.append((selector, value, timeout))

        def locator(self, selector):
            class _Locator:
                async def wait_for(self, state=None, timeout=None):
                    raise RuntimeError("not visible")

            return _Locator()

        async def inner_text(self, selector):
            return "欢迎回来 用户A"

    page = _Page()
    result = asyncio.run(wlc._execute_step(page, "fill", {"selector": "#user", "value": "u1"}, 1500))
    assert result == {"success": True}
    assert page.fills == [("#user", "u1", 1500)]

    result = asyncio.run(wlc._execute_step(page, "assert_text", {"text": "用户A"}, 1500))
    assert result == {"success": True}


def test_execute_step_with_asset_fallback_first_success(monkeypatch):
    calls = []

    async def _ok_step(page, action, params, timeout_ms):
        calls.append(dict(params))
        return {"success": True, "selector": params.get("selector")}

    monkeypatch.setattr(wlc, "_execute_step", _ok_step)
    params = {"selector": "#a", "_asset_selectors": ["#a", "#b"]}
    result = asyncio.run(wlc._execute_step_with_asset_fallback(object(), "click", params, 1000))
    assert result == {"success": True, "selector": "#a"}
    assert len(calls) == 1


def test_expand_page_object_steps_alias_refs_and_missing_asset():
    class _DB:
        def __init__(self, page_object):
            self.page_object = page_object

        async def get(self, model, pk):
            return self.page_object

    po = types.SimpleNamespace(
        project_id=5,
        element_refs=["junk", {"alias": None}, {"alias": "login", "asset_id": 11}],
        actions=[
            {"step": "click", "element": "login"},
            {"step": "input", "element": "missing"},
            {"step": "click", "asset_id": 0},
        ],
    )
    expanded, err = asyncio.run(
        wlc._expand_page_object_steps(_DB(po), [{"action": "page_object", "params": {"page_object_id": 1}}], 5)
    )
    assert err is None and len(expanded) == 3
    assert expanded[0]["params"]["element_asset_id"] == 11
    assert "element_asset_id" not in expanded[1]["params"]
    assert expanded[2]["params"]["element_asset_id"] == 0


def test_run_web_lowcode_skips_matrix_when_variant_flag_set(monkeypatch):
    events, _page, _ctx = _install_web_env(monkeypatch)
    db, run, case = _run_entities(
        [{"action": "goto", "params": {"url": "https://demo"}}], cfg={"_web_matrix_variant": True}
    )
    asyncio.run(wlc.run_web_lowcode(db, run, case, {}))
    assert run.status == RunStatus.passed
    assert events.acquire_kwargs is not None


def test_run_web_lowcode_page_object_expansion_success(monkeypatch):
    events, _page, _ctx = _install_web_env(monkeypatch)

    async def _expand(db_arg, steps_arg, project_id):
        assert project_id == 5
        return [{"action": "goto", "params": {"url": "https://demo"}}], None

    monkeypatch.setattr(wlc, "_expand_page_object_steps", _expand)
    db, run, case = _run_entities([{"action": "page_object", "params": {"page_object_id": 3}}])
    asyncio.run(wlc.run_web_lowcode(db, run, case, {}))
    assert run.status == RunStatus.passed


def test_run_web_lowcode_use_storage_state_without_project(monkeypatch):
    events, _page, _ctx = _install_web_env(monkeypatch)
    calls = []
    monkeypatch.setattr(wlc, "read_bytes", lambda name: calls.append(name) or b"x")
    db, run, case = _run_entities(
        [{"action": "goto", "params": {"url": "https://demo"}}],
        cfg={"use_storage_state": "login"},
        project_id=None,
    )
    asyncio.run(wlc.run_web_lowcode(db, run, case, {}))
    assert run.status == RunStatus.passed
    assert calls == []
    assert "storage_state" not in events.acquire_kwargs["context_options"]


def test_run_web_lowcode_use_storage_state_empty_bytes(monkeypatch):
    events, _page, _ctx = _install_web_env(monkeypatch)
    calls = []
    monkeypatch.setattr(wlc, "read_bytes", lambda name: calls.append(name) or b"")
    db, run, case = _run_entities(
        [{"action": "goto", "params": {"url": "https://demo"}}], cfg={"use_storage_state": "login"}
    )
    asyncio.run(wlc.run_web_lowcode(db, run, case, {}))
    assert run.status == RunStatus.passed
    assert calls == ["storage-states/projects/5/login.json"]
    assert "storage_state" not in events.acquire_kwargs["context_options"]


class _NoOnPage(_FakePage):
    @property
    def on(self):
        raise AttributeError("no event handlers")


def test_run_web_lowcode_page_without_event_handlers(monkeypatch):
    page = _NoOnPage()
    events, page, context = _install_web_env(monkeypatch, page=page)
    db, run, case = _run_entities([{"action": "goto", "params": {"url": "https://demo"}}])
    asyncio.run(wlc.run_web_lowcode(db, run, case, {}))
    assert run.status == RunStatus.passed
    assert page.handlers == {}


def test_run_web_lowcode_dead_browser_marks_step_failed(monkeypatch):
    browser = types.SimpleNamespace(is_connected=lambda: False)
    events, _page, _ctx = _install_web_env(monkeypatch, browser=browser)
    db, run, case = _run_entities([{"action": "click", "params": {"selector": "#a"}}])
    asyncio.run(wlc.run_web_lowcode(db, run, case, {}))
    assert run.status == RunStatus.failed
    assert db.added[0].error_message == "浏览器进程已断开"


def test_run_web_lowcode_heal_failure_keeps_step_failed(monkeypatch):
    events, _page, _ctx = _install_web_env(monkeypatch)
    monkeypatch.setattr(wlc, "is_locator_failure", lambda message: True)

    async def _failing_step(*args, **kwargs):
        return {"success": False, "error": "locator timeout"}

    async def _heal_fail(page_arg, action, params, timeout_ms, **kwargs):
        events.healed = True
        return {"success": False}

    monkeypatch.setattr(wlc, "_execute_step", _failing_step)
    monkeypatch.setattr(
        wlc,
        "runtime_locator_healer",
        types.SimpleNamespace(attempt_heal_and_retry=_heal_fail, reset_run=lambda rid: events.reset_runs.append(rid)),
    )
    db, run, case = _run_entities([{"action": "click", "params": {"selector": "#flaky"}}])
    asyncio.run(wlc.run_web_lowcode(db, run, case, {}))
    assert run.status == RunStatus.failed
    assert getattr(events, "healed", False) is True
    assert db.added[0].error_message == "locator timeout"
    assert events.reset_runs == [99]


def test_run_web_lowcode_step_exception_marks_failed(monkeypatch):
    events, _page, _ctx = _install_web_env(monkeypatch)

    async def _boom_step(*args, **kwargs):
        raise RuntimeError("step exploded")

    monkeypatch.setattr(wlc, "_execute_step_with_asset_fallback", _boom_step)
    db, run, case = _run_entities([{"action": "click", "params": {"selector": "#a"}}])
    asyncio.run(wlc.run_web_lowcode(db, run, case, {}))
    assert run.status == RunStatus.failed
    assert db.added[0].error_message == "step exploded"


def test_run_web_lowcode_route_failure_hits_run_level_except(monkeypatch):
    events, _page, context = _install_web_env(monkeypatch)

    async def _boom_route(pattern, handler):
        raise RuntimeError("route boom")

    monkeypatch.setattr(context, "route", _boom_route)
    db, run, case = _run_entities([{"action": "goto", "params": {"url": "https://demo"}}])
    asyncio.run(wlc.run_web_lowcode(db, run, case, {}))
    assert run.status == RunStatus.failed
    assert "route boom" in run.error_message
    assert len(events.released) == 1
    assert events.reset_runs == [99]


def test_run_web_lowcode_save_storage_state_without_project(monkeypatch):
    events, _page, _ctx = _install_web_env(monkeypatch)
    db, run, case = _run_entities(
        [{"action": "goto", "params": {"url": "https://demo"}}],
        cfg={"save_storage_state": "login"},
        project_id=None,
    )
    asyncio.run(wlc.run_web_lowcode(db, run, case, {}))
    assert run.status == RunStatus.passed
    assert not any(name.startswith("storage-states/") for name, _data, _ct in events.uploaded)
