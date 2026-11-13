"""补充 backend/app/api/v1/web_recordings.py 的覆盖率缺口。

覆盖审计基线中缺失的分支：本地模式 URL 校验、启动链路的 display/tracing/replay
分支、回放单步动作、事件处理器、归档失败路径、远程 Worker 错误映射与元素持久化边界。
"""

import asyncio
import json
from pathlib import Path
from types import SimpleNamespace

import pytest
from fastapi import HTTPException

from app.api.v1 import web_recordings
from app.api.v1.web_recordings import (
    WebRecordingManager,
    WebRecordingSession,
    WebRecordingStart,
    _persist_recorded_assets,
    _safe_headers,
    _sanitize_har,
)
from app.models.bootstrap import load_all_models
from app.services.web_recording_transport import WebRecordingTransportError

load_all_models()


def _session(page=None, **overrides):
    params = dict(
        session_id="gap-session",
        owner_id=1,
        start_url="https://example.com",
        viewport_width=1280,
        viewport_height=720,
        status="recording",
        page=page,
    )
    params.update(overrides)
    return WebRecordingSession(**params)


def _stub_artifacts(monkeypatch):
    monkeypatch.setattr(web_recordings, "upload_file", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(web_recordings, "presigned_url", lambda object_name: f"https://minio.test/{object_name}")


class _FakeTracing:
    def __init__(self):
        self.start_kwargs = None
        self.stopped_with = None

    async def start(self, **kwargs):
        self.start_kwargs = kwargs

    async def stop(self, path=None):
        self.stopped_with = path


class _Page:
    def __init__(self, *, url="about:blank", goto_error=None):
        self.url = url
        self.handlers = {}
        self.scripts = []
        self.bindings = []
        self.gotos = []
        self.evaluated = []
        self.goto_error = goto_error

    async def expose_binding(self, name, handler):
        self.bindings.append((name, handler))

    async def add_init_script(self, script):
        self.scripts.append(script)

    def on(self, event, handler):
        self.handlers[event] = handler

    async def goto(self, url, **_kwargs):
        if self.goto_error is not None:
            raise self.goto_error
        self.gotos.append(url)
        self.url = url

    async def evaluate(self, script):
        self.evaluated.append(script)

    async def screenshot(self, **_kwargs):
        return b"png"


class _Context:
    def __init__(self, page, tracing=None):
        self.page = page
        self.tracing = tracing
        self.routes = []
        self.handlers = {}

    async def route(self, pattern, handler):
        self.routes.append((pattern, handler))

    async def new_page(self):
        return self.page

    def on(self, event, handler):
        self.handlers[event] = handler

    async def close(self):
        pass


class _Browser:
    def __init__(self, context):
        self.context = context
        self.handlers = {}
        self.closed = False

    async def new_context(self, **_kwargs):
        return self.context

    def on(self, event, handler):
        self.handlers[event] = handler

    async def close(self):
        self.closed = True


class _Factory:
    def __init__(self, page=None, tracing=None):
        page = page if page is not None else _Page()
        self.page = page
        self.context = _Context(page, tracing)
        self.browser = _Browser(self.context)
        self.launch_args = None
        self.stopped = False
        launcher = SimpleNamespace(launch=self._launch)
        self.playwright = SimpleNamespace(chromium=launcher, firefox=launcher, webkit=launcher, stop=self._stop)

    async def _launch(self, **kwargs):
        self.launch_args = kwargs
        return self.browser

    async def _stop(self):
        self.stopped = True

    async def start(self):
        return self.playwright


def test_safe_headers_skips_malformed_items_and_redacts_credentials():
    result = _safe_headers(
        [
            {"name": "Accept", "value": "application/json"},
            "not-a-dict",
            {"name": "", "value": "x"},
            {"name": "Authorization", "value": "Bearer secret"},
        ]
    )

    assert result == [
        {"name": "Accept", "value": "application/json"},
        {"name": "Authorization", "value": "<redacted>"},
    ]


def test_sanitize_har_rejects_missing_entries_and_tolerates_bad_shapes():
    with pytest.raises(ValueError, match="entries"):
        _sanitize_har(b'{"log": {}}')

    payload = {
        "log": {
            "entries": [
                "skip-me",
                {"request": "bad", "response": "bad"},
                {"request": {"url": "https://e/x?token=secret"}, "response": {"headers": "nope"}},
            ]
        }
    }
    out = json.loads(_sanitize_har(json.dumps(payload).encode()))

    assert out["log"]["entries"][0] == "skip-me"
    assert out["log"]["entries"][1] == {"request": "bad", "response": "bad"}
    assert out["log"]["entries"][2]["request"]["cookies"] == []
    assert out["log"]["entries"][2]["response"]["cookies"] == []


def test_start_url_validator_local_mode_paths(monkeypatch):
    monkeypatch.setattr(web_recordings.settings, "ATP_LOCAL_MODE", True)
    monkeypatch.setattr(web_recordings, "validate_browser_request_url", lambda value: value + "/checked")

    payload = WebRecordingStart(start_url="http://example.com", project_id=1)
    assert payload.start_url == "http://example.com/checked"

    with pytest.raises(ValueError, match="http 或 https"):
        WebRecordingStart(start_url="ftp://example.com", project_id=1)


def test_start_requires_display_on_linux(monkeypatch):
    factory = _Factory()
    monkeypatch.setattr(web_recordings, "async_playwright", lambda: factory)
    monkeypatch.setattr(web_recordings.sys, "platform", "linux")
    monkeypatch.setattr(web_recordings.settings, "WEB_RECORDER_DISPLAY", "")
    monkeypatch.delenv("DISPLAY", raising=False)
    session = _session(page=None, status="starting")

    with pytest.raises(RuntimeError, match="X display"):
        asyncio.run(session.start())

    assert session.status == "error"
    assert "X display" in session.error
    assert factory.stopped is True


def test_start_without_display_omits_display_env(monkeypatch):
    factory = _Factory()
    monkeypatch.setattr(web_recordings, "async_playwright", lambda: factory)
    monkeypatch.setattr(web_recordings.settings, "WEB_RECORDER_DISPLAY", "")
    monkeypatch.delenv("DISPLAY", raising=False)
    # Linux 上「无 display」会在 start() 前段按设计直接拒绝（由 test_start_requires_display_on_linux 覆盖）；
    # 本用例验证非 Linux 路径：未解析出 display 时不应向浏览器进程注入 DISPLAY。
    monkeypatch.setattr(web_recordings.sys, "platform", "darwin")
    _stub_artifacts(monkeypatch)
    session = _session(page=None, status="starting")

    asyncio.run(session.start())

    assert session.status == "recording"
    assert "DISPLAY" not in factory.launch_args["env"]
    assert factory.launch_args["headless"] is False
    asyncio.run(session.stop())


def test_start_registers_tracing_and_close_handlers(monkeypatch):
    tracing = _FakeTracing()
    factory = _Factory(tracing=tracing)
    monkeypatch.setattr(web_recordings, "async_playwright", lambda: factory)
    monkeypatch.setattr(web_recordings.settings, "WEB_RECORDER_DISPLAY", ":99")
    _stub_artifacts(monkeypatch)
    session = _session(page=None, status="starting")

    asyncio.run(session.start())

    assert tracing.start_kwargs == {"screenshots": True, "snapshots": True, "sources": False}
    assert session.trace_started is True
    assert "close" in factory.context.handlers
    assert "disconnected" in factory.browser.handlers
    assert "close" in factory.page.handlers

    asyncio.run(session.stop())
    assert tracing.stopped_with == str(session.trace_path)
    assert session.trace_started is False


def test_start_replays_recorded_prefix_and_evaluates_script(monkeypatch):
    factory = _Factory()
    monkeypatch.setattr(web_recordings, "async_playwright", lambda: factory)
    monkeypatch.setattr(web_recordings.settings, "WEB_RECORDER_DISPLAY", ":99")
    _stub_artifacts(monkeypatch)
    session = _session(
        page=None,
        status="starting",
        replay_steps=[{"action": "goto", "params": {"url": "https://example.com/step1"}}],
    )

    asyncio.run(session.start())

    assert session.is_resuming is True
    assert session.replayed_step_count == 1
    assert factory.page.gotos == ["https://example.com/step1"]
    assert factory.page.evaluated == [web_recordings._RECORDING_SCRIPT]
    assert session.status == "recording"
    asyncio.run(session.stop())


def test_start_stops_replaying_after_step_failure(monkeypatch):
    factory = _Factory()
    factory.page.goto_error = RuntimeError("navigation failed")
    monkeypatch.setattr(web_recordings, "async_playwright", lambda: factory)
    monkeypatch.setattr(web_recordings.settings, "WEB_RECORDER_DISPLAY", ":99")
    _stub_artifacts(monkeypatch)
    session = _session(
        page=None,
        status="starting",
        replay_steps=[
            {"action": "goto", "params": {"url": "https://example.com/step1"}},
            {"action": "goto", "params": {"url": "https://example.com/step2"}},
        ],
    )

    asyncio.run(session.start())

    assert session.replayed_step_count == 0
    assert factory.page.gotos == []
    assert session.status == "recording"
    asyncio.run(session.stop())


def test_start_tolerates_page_without_close_support(monkeypatch):
    class _FlakyOnPage(_Page):
        def __init__(self):
            super().__init__()
            self._on_accesses = 0

        @property
        def on(self):
            self._on_accesses += 1
            if self._on_accesses >= 9:
                raise AttributeError("on")
            return super().on

    factory = _Factory(page=_FlakyOnPage())
    monkeypatch.setattr(web_recordings, "async_playwright", lambda: factory)
    monkeypatch.setattr(web_recordings.settings, "WEB_RECORDER_DISPLAY", ":99")
    _stub_artifacts(monkeypatch)
    session = _session(page=None, status="starting")

    asyncio.run(session.start())

    assert session.status == "recording"
    assert "close" not in factory.page.handlers
    asyncio.run(session.stop())


def test_replay_single_step_covers_action_branches(monkeypatch):
    calls = []
    sleeps = []

    async def _sleep(delay):
        sleeps.append(delay)

    monkeypatch.setattr(web_recordings, "asyncio", SimpleNamespace(sleep=_sleep))

    class _Keyboard:
        async def press(self, key):
            calls.append(("press", key))

    class _StepPage:
        def __init__(self):
            self.keyboard = _Keyboard()

        async def goto(self, url, **kwargs):
            calls.append(("goto", url))

        async def click(self, selector, **kwargs):
            calls.append(("click", selector))

        async def fill(self, selector, value, **kwargs):
            calls.append(("fill", selector, value))

        async def select_option(self, selector, **kwargs):
            calls.append(("select", selector, kwargs.get("value")))

        async def hover(self, selector, **kwargs):
            calls.append(("hover", selector))

    session = _session(page=_StepPage())
    asyncio.run(session._replay_single_step("goto", {}))
    asyncio.run(session._replay_single_step("click", {}))
    asyncio.run(session._replay_single_step("fill", {"selector": "#a", "value": "x"}))
    asyncio.run(session._replay_single_step("select", {"selector": "#b", "value": "v"}))
    asyncio.run(session._replay_single_step("hover", {"selector": "#c"}))
    asyncio.run(session._replay_single_step("press", {"key": "Enter"}))
    asyncio.run(session._replay_single_step("press", {}))
    asyncio.run(session._replay_single_step("fill", {"value": "x"}))
    asyncio.run(session._replay_single_step("select", {"value": "v"}))
    asyncio.run(session._replay_single_step("hover", {}))
    asyncio.run(session._replay_single_step("noop", {}))

    assert calls == [
        ("fill", "#a", "x"),
        ("select", "#b", "v"),
        ("hover", "#c"),
        ("press", "Enter"),
    ]
    assert sleeps

    empty = _session(page=None)
    asyncio.run(empty._replay_single_step("goto", {"url": "https://example.com"}))


def test_stop_is_noop_for_finished_sessions():
    async def _boom():
        raise AssertionError("close should not run")

    for status in ("stopped", "error"):
        session = _session(page=None, status=status)
        session.close = _boom
        asyncio.run(session.stop())
        assert session.status == status


def test_screenshot_wraps_page_failures():
    class _BrokenPage:
        def is_closed(self):
            return False

        async def screenshot(self, **_kwargs):
            raise ValueError("crash")

    session = _session(page=_BrokenPage())

    with pytest.raises(RuntimeError, match="不可截图"):
        asyncio.run(session.screenshot())


def test_current_url_skips_non_http_and_handles_page_errors():
    class _NonHttpPage:
        url = "about:blank"

        def is_closed(self):
            return False

    session = _session(page=_NonHttpPage())
    assert session.current_url() == "https://example.com"

    class _RaisingPage:
        def is_closed(self):
            return False

        @property
        def url(self):
            raise RuntimeError("gone")

    fallback = _session(page=_RaisingPage())
    fallback.steps = [{"action": "goto", "params": {"url": "https://example.com/last"}}]
    assert fallback.current_url() == "https://example.com/last"


def test_close_handlers_noop_when_finished_and_outside_loop():
    finished = _session(page=None, status="stopped")
    finished._handle_page_close()
    finished._handle_context_close()
    finished._handle_browser_disconnect()

    active = _session(page=None, status="recording")
    # 无运行中的事件循环：get_running_loop 抛 RuntimeError 时必须静默吞掉
    active._handle_page_close()
    active._handle_context_close()
    active._handle_browser_disconnect()
    assert active.status == "recording"


def test_append_capped_respects_limit():
    session = _session(page=None)
    target = [{"i": 0}]
    session._append_capped(target, {"i": 1}, limit=1)
    assert target == [{"i": 0}]

    session._append_capped(target, {"i": 1}, limit=2)
    assert len(target) == 2


def test_event_handlers_record_sanitized_details():
    session = _session(page=None)
    session._handle_console(SimpleNamespace(type="warning", text="hello"))
    session._handle_page_error("boom")
    session._handle_request(SimpleNamespace(method="POST", url="https://e/api?token=secret", resource_type="xhr"))

    assert session.console_messages == [{"type": "warning", "text": "hello"}]
    assert session.page_errors == [{"message": "boom"}]
    assert session.network_events[0]["type"] == "request"
    assert session.network_events[0]["method"] == "POST"
    assert session.network_events[0]["resource_type"] == "xhr"
    assert "secret" not in session.network_events[0]["url"]


def test_failed_and_response_handlers_cover_branches():
    session = _session(page=None)

    failing = SimpleNamespace(
        method="GET",
        url="https://e/api",
        resource_type="fetch",
        failure=lambda: "net::ERR_TIMED_OUT",
    )
    session._handle_request_failed(failing)
    no_failure = SimpleNamespace(method="GET", url="https://e/ok", resource_type="fetch", failure=None)
    session._handle_request_failed(no_failure)

    assert session.failed_requests[0]["error"] == "net::ERR_TIMED_OUT"
    assert session.failed_requests[1]["error"] == "request failed"
    assert session.network_events[0] == {"type": "request_failed", **session.failed_requests[0]}

    session._handle_response(SimpleNamespace(request=None, status=200))

    request = SimpleNamespace(method="GET", url="https://e/x", resource_type="document")
    session._handle_response(SimpleNamespace(request=request, status="oops"))
    session._handle_response(SimpleNamespace(request=request, status=500))

    assert session.network_events[-2]["status"] == 0
    assert session.error_responses[-1]["status"] == 500


def test_stop_tracing_records_artifact_error():
    class _Tracing:
        async def stop(self, path=None):
            raise RuntimeError("trace busy")

    session = _session(page=None, trace_started=True, trace_path=Path("trace.zip"))
    session.context = SimpleNamespace(tracing=_Tracing())

    asyncio.run(session._stop_tracing())

    assert session.trace_started is False
    assert "Trace 保存失败" in session.artifact_error


def test_report_events_sanitizes_urls_and_errors():
    events = [
        {"type": "response", "status": 500, "error": "failed at https://e/x?token=secret"},
        {"type": "response", "url": "https://e/y?token=secret", "status": 200},
    ]
    result = WebRecordingSession._report_events(events, 2)

    assert len(result) == 2
    assert "secret" not in result[0]["error"]
    assert "secret" not in result[1]["url"]


def test_persist_artifacts_collects_failures(monkeypatch, tmp_path):
    def _boom(*_args, **_kwargs):
        raise RuntimeError("minio down")

    monkeypatch.setattr(web_recordings, "upload_file", _boom)
    monkeypatch.setattr(web_recordings, "presigned_url", lambda _o: "https://minio/x")

    artifact_dir = tmp_path / "a"
    artifact_dir.mkdir()
    har_path = artifact_dir / "network.har"
    har_path.write_bytes(b"not-json")
    trace_path = artifact_dir / "trace.zip"
    trace_path.write_bytes(b"trace")
    session = _session(
        page=None,
        status="stopping",
        artifact_dir=artifact_dir,
        trace_path=trace_path,
        har_path=har_path,
        report_path=None,
    )

    asyncio.run(session._persist_artifacts())

    assert session.artifacts == {}
    assert "HAR 脱敏失败" in session.artifact_error
    assert "trace 上传失败" in session.artifact_error
    assert "har 上传失败" in session.artifact_error


def test_persist_artifacts_marks_report_upload_failure(monkeypatch, tmp_path):
    def _upload(object_name, _path, _content_type):
        if object_name.endswith("report.json"):
            raise RuntimeError("report upload down")

    monkeypatch.setattr(web_recordings, "upload_file", _upload)
    monkeypatch.setattr(web_recordings, "presigned_url", lambda o: f"https://minio/{o}")

    artifact_dir = tmp_path / "b"
    artifact_dir.mkdir()
    report_path = artifact_dir / "report.json"
    session = _session(
        page=None,
        status="stopping",
        project_id=3,
        artifact_dir=artifact_dir,
        report_path=report_path,
    )

    asyncio.run(session._persist_artifacts())

    assert session.artifacts == {}
    assert "运行报告上传失败" in session.artifact_error


def test_navigation_handler_covers_frame_and_resume_branches():
    main_frame = SimpleNamespace(url="https://example.com/page")
    session = _session(page=SimpleNamespace(main_frame=main_frame))

    session._handle_navigation(SimpleNamespace(url="https://ads.example.com/x"))
    assert session.steps == []

    main_frame.url = "about:blank"
    session._handle_navigation(main_frame)
    assert session.steps == []

    main_frame.url = "https://example.com/page"
    session.steps = [{"action": "goto", "name": "打开页面", "params": {"url": "https://example.com/page"}}]
    session._handle_navigation(main_frame)
    assert len(session.steps) == 1

    session.steps = []
    main_frame.url = "https://example.com/next"
    session._handle_navigation(main_frame)
    assert session.steps[-1]["action"] == "goto"
    assert session.steps[-1]["params"]["url"] == "https://example.com/next"

    resuming = _session(page=SimpleNamespace(main_frame=SimpleNamespace(url="https://example.com/replayed/")))
    resuming.is_resuming = True
    resuming.replay_steps = [{"action": "goto", "params": {"url": "https://example.com/replayed"}}]
    resuming._handle_navigation(resuming.page.main_frame)
    assert resuming.steps == []

    resuming_other = _session(page=SimpleNamespace(main_frame=SimpleNamespace(url="https://example.com/other")))
    resuming_other.is_resuming = True
    resuming_other.replay_steps = [{"action": "goto", "params": {"url": "https://example.com/replayed"}}]
    resuming_other._handle_navigation(resuming_other.page.main_frame)
    assert resuming_other.steps[-1]["params"]["url"] == "https://example.com/other"

    resuming_fallback = _session(page=SimpleNamespace(main_frame=SimpleNamespace(url="https://example.com")))
    resuming_fallback.is_resuming = True
    resuming_fallback.replay_steps = [{"action": "click", "params": {"selector": "#a"}}]
    resuming_fallback._handle_navigation(resuming_fallback.page.main_frame)
    assert resuming_fallback.steps == []

    resuming_empty_step = _session(page=SimpleNamespace(main_frame=SimpleNamespace(url="https://example.com/x")))
    resuming_empty_step.is_resuming = True
    resuming_empty_step.replay_steps = [
        {"action": "goto", "params": {"url": "https://example.com/x"}},
        {"action": "goto", "params": {}},
    ]
    resuming_empty_step._handle_navigation(resuming_empty_step.page.main_frame)
    assert resuming_empty_step.steps == []


def test_binding_and_select_events_append_steps():
    session = _session(page=None)
    session._handle_binding(None, "ignored")
    assert session.steps == []

    session._handle_binding(None, {"type": "select", "selector": "#city", "value": "sh"})
    session._handle_binding(None, {"type": "hover"})
    assert session.steps == [
        {"action": "select", "name": "选择 #city", "params": {"selector": "#city", "value": "sh"}},
    ]

    session._handle_binding(None, {"type": "press", "selector": "#q"})
    assert session.steps[-1]["name"] == "按键 Enter"


def test_manager_start_failure_removes_session(monkeypatch):
    async def _fail(_self):
        raise RuntimeError("spawn failed")

    monkeypatch.setattr(WebRecordingSession, "start", _fail)
    manager = WebRecordingManager()
    payload = WebRecordingStart(start_url="https://example.com", project_id=1)

    with pytest.raises(HTTPException) as exc:
        asyncio.run(manager.start(payload, owner_id=1))

    assert exc.value.status_code == 400
    assert "无法启动录制浏览器" in exc.value.detail
    assert manager.sessions == {}


def test_worker_status_route_maps_transport_error(monkeypatch):
    monkeypatch.setattr(web_recordings.settings, "WEB_RECORDER_MODE", "worker")

    async def _boom():
        raise WebRecordingTransportError("录制 Worker 注册中心不可用")

    monkeypatch.setattr(web_recordings, "list_recording_workers", _boom)

    with pytest.raises(HTTPException) as exc:
        asyncio.run(web_recordings.get_recording_workers(SimpleNamespace(id=1)))

    assert exc.value.status_code == 503
    assert exc.value.detail == "录制 Worker 注册中心不可用"


def test_recording_routes_map_transport_errors(monkeypatch):
    monkeypatch.setattr(web_recordings.settings, "WEB_RECORDER_MODE", "worker")
    monkeypatch.setattr(web_recordings, "assert_project_access", lambda *_args, **_kwargs: asyncio.sleep(0))
    monkeypatch.setattr(web_recordings, "validate_public_http_url", lambda url: url)
    monkeypatch.setattr(web_recordings, "validate_browser_request_url", lambda url: url)

    class _DB:
        async def get(self, _model, _project_id):
            return SimpleNamespace(id=1)

    def _raiser(method):
        async def _raise(*_args, **_kwargs):
            raise WebRecordingTransportError(f"{method} 失败", 409)

        return _raise

    for method in ("start", "get", "screenshot", "stop"):
        monkeypatch.setattr(web_recordings.remote_manager, method, _raiser(method))

    payload = WebRecordingStart(start_url="https://example.com", project_id=1)
    user = SimpleNamespace(id=5)

    with pytest.raises(HTTPException) as exc:
        asyncio.run(web_recordings.start_recording(payload, _DB(), user))
    assert (exc.value.status_code, exc.value.detail) == (409, "start 失败")

    with pytest.raises(HTTPException) as exc:
        asyncio.run(web_recordings.get_recording("s1", user))
    assert exc.value.status_code == 409

    with pytest.raises(HTTPException) as exc:
        asyncio.run(web_recordings.capture_recording_screenshot("s1", user))
    assert exc.value.status_code == 409

    with pytest.raises(HTTPException) as exc:
        asyncio.run(web_recordings.stop_recording("s1", _DB(), user))
    assert exc.value.status_code == 409


def test_persist_assets_skips_when_no_project_or_already_persisted():
    class _ExplodingDB:
        async def execute(self, _query):
            raise AssertionError("no db access expected")

    no_project = _session(page=None, project_id=None)
    asyncio.run(_persist_recorded_assets(_ExplodingDB(), no_project))
    assert no_project.assets_persisted is False

    already = _session(page=None, project_id=1, assets_persisted=True)
    asyncio.run(_persist_recorded_assets(_ExplodingDB(), already))
    assert already.assets_persisted is True


def test_persist_assets_leaves_unmatched_selector_steps_untouched():
    class _Rows:
        def scalars(self):
            return self

        def all(self):
            return []

    class _DB:
        def __init__(self):
            self.items = []

        def add(self, item):
            item.id = len(self.items) + 1
            self.items.append(item)

        async def execute(self, _query):
            return _Rows()

        async def flush(self):
            return None

        async def commit(self):
            return None

    session = _session(
        page=None,
        project_id=6,
        steps=[
            {"action": "click", "name": "点击登录", "params": {"selector": "#login"}},
            {
                "action": "goto",
                "name": "打开页面",
                "params": {"selector": "#not-collected", "url": "https://example.com"},
            },
        ],
    )
    db = _DB()

    asyncio.run(_persist_recorded_assets(db, session))

    assert len(db.items) == 1
    assert session.steps[0]["params"]["element_asset_id"] == 1
    assert "element_asset_id" not in session.steps[1]["params"]


def test_close_all_recordings_delegates_to_manager(monkeypatch):
    closed = []

    async def _close_all():
        closed.append(True)

    monkeypatch.setattr(web_recordings.manager, "close_all", _close_all)
    asyncio.run(web_recordings.close_all_recordings())
    assert closed == [True]


def test_recording_worker_status_boundaries():
    assert web_recordings._recording_worker_status({"worker_id": "   "}) is None

    healthy = web_recordings._recording_worker_status(
        {"worker_id": "node-1", "active_sessions": 2, "capacity": 3, "updated_at": 123.5}
    )
    assert healthy["worker_id"].startswith("worker-")
    assert healthy["active_sessions"] == 2
    assert healthy["capacity"] == 3

    degraded = web_recordings._recording_worker_status(
        {"worker_id": "node-2", "active_sessions": "bad", "capacity": None, "updated_at": "not-a-time"}
    )
    assert degraded["active_sessions"] == 0
    assert degraded["capacity"] == 1


def test_stop_tracing_without_tracing_object():
    session = _session(page=None, trace_started=True, trace_path=Path("trace.zip"))
    session.context = SimpleNamespace()

    asyncio.run(session._stop_tracing())

    assert session.trace_started is False
    assert session.artifact_error is None
