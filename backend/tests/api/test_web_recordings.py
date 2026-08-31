import asyncio
import json
from types import SimpleNamespace

import pytest
from fastapi import HTTPException

from app.api.v1.web_recordings import (
    _RECORDING_SCRIPT,
    _safe_text,
    _sanitize_har,
    _persist_recorded_assets,
    WebRecordingManager,
    WebRecordingSession,
    WebRecordingStart,
)
from app.models.bootstrap import load_all_models
from app.models.web_assets import WebElementAsset

load_all_models()


def test_recording_start_requires_http_url():
    with pytest.raises(ValueError):
        WebRecordingStart(start_url="file:///tmp/page.html", project_id=1)


@pytest.mark.parametrize(
    "url",
    [
        "http://localhost/admin",
        "http://127.0.0.1:8000/metrics",
        "http://169.254.169.254/latest/meta-data",
        "http://[::1]/",
    ],
)
def test_recording_start_rejects_explicit_internal_addresses(url):
    with pytest.raises(ValueError):
        WebRecordingStart(start_url=url, project_id=1)


def test_recording_start_validates_project_and_browser():
    with pytest.raises(ValueError):
        WebRecordingStart(start_url="https://example.com")
    assert WebRecordingStart(start_url="https://example.com", project_id=1, browser="firefox").browser == "firefox"
    assert WebRecordingStart(start_url="https://example.com", project_id=1, browser="webkit").browser == "webkit"
    with pytest.raises(ValueError):
        WebRecordingStart(start_url="https://example.com", project_id=1, browser="safari")


def test_recording_events_become_lowcode_steps_and_fill_is_coalesced():
    session = WebRecordingSession(
        session_id="test-session",
        owner_id=1,
        start_url="https://example.com",
        viewport_width=1280,
        viewport_height=720,
        status="recording",
    )

    session._append_event({"type": "input", "selector": "#username", "value": "a"})
    session._append_event({"type": "input", "selector": "#username", "value": "alice"})
    session._append_event({"type": "click", "selector": "button[type=submit]"})
    session._append_event({"type": "press", "selector": "#username", "key": "Enter"})

    assert session.steps == [
        {
            "action": "fill",
            "name": "输入 #username",
            "params": {"selector": "#username", "value": "alice"},
        },
        {
            "action": "click",
            "name": "点击 button[type=submit]",
            "params": {"selector": "button[type=submit]"},
        },
        {
            "action": "press",
            "name": "按键 Enter",
            "params": {"key": "Enter", "selector": "#username"},
        },
    ]


def test_recording_does_not_store_password_value():
    session = WebRecordingSession(
        session_id="test-session",
        owner_id=1,
        start_url="https://example.com",
        viewport_width=1280,
        viewport_height=720,
        status="recording",
    )

    session._append_event({"type": "input", "selector": "#password", "value": "", "sensitive": True})

    assert session.steps[0]["params"] == {"selector": "#password", "value": ""}
    assert "敏感值" in session.steps[0]["name"]


def test_recording_har_evidence_is_redacted_before_persistence():
    raw = json.dumps(
        {
            "log": {
                "entries": [
                    {
                        "request": {
                            "url": "https://example.com/login?token=secret&next=/home",
                            "headers": [
                                {"name": "Authorization", "value": "Bearer secret"},
                                {"name": "Accept", "value": "application/json"},
                            ],
                            "cookies": [{"name": "session", "value": "secret"}],
                            "postData": {"text": "password=secret"},
                        },
                        "response": {
                            "headers": [{"name": "Set-Cookie", "value": "session=secret"}],
                            "cookies": [{"name": "session", "value": "secret"}],
                            "content": {"text": "secret response"},
                        },
                    }
                ]
            }
        }
    ).encode()

    sanitized = json.loads(_sanitize_har(raw))
    request = sanitized["log"]["entries"][0]["request"]
    response = sanitized["log"]["entries"][0]["response"]
    assert "secret" not in json.dumps(sanitized)
    assert request["url"] == "https://example.com/login?token=%2A%2A%2A&next=%2Fhome"
    assert request["cookies"] == []
    assert "postData" not in request
    assert response["cookies"] == []
    assert "content" not in response


def test_recording_text_evidence_redacts_json_credentials_and_urls():
    sanitized = _safe_text(
        'login failed: {"password":"secret","token":"abc"} ' "https://example.com/login?api_key=private&next=/home"
    )

    assert "secret" not in sanitized
    assert "abc" not in sanitized
    assert "private" not in sanitized
    assert "api_key=<redacted>" in sanitized


def test_recording_persists_trace_har_and_report_artifacts(monkeypatch, tmp_path):
    import app.api.v1.web_recordings as web_recordings

    uploaded: list[tuple[str, str, str]] = []

    def upload(object_name, path, content_type):
        uploaded.append((object_name, str(path), content_type))

    monkeypatch.setattr(web_recordings, "upload_file", upload)
    monkeypatch.setattr(web_recordings, "presigned_url", lambda object_name: f"https://minio.test/{object_name}")

    artifact_dir = tmp_path / "artifacts"
    artifact_dir.mkdir()
    trace_path = artifact_dir / "trace.zip"
    har_path = artifact_dir / "network.har"
    report_path = artifact_dir / "report.json"
    trace_path.write_bytes(b"trace")
    har_path.write_text(
        json.dumps({"log": {"entries": [{"request": {"url": "https://example.com?token=secret"}}]}}),
        encoding="utf-8",
    )
    session = WebRecordingSession(
        session_id="artifact-session",
        owner_id=1,
        project_id=7,
        start_url="https://example.com?token=secret",
        viewport_width=1280,
        viewport_height=720,
        status="stopping",
        artifact_dir=artifact_dir,
        trace_path=trace_path,
        har_path=har_path,
        report_path=report_path,
        steps=[{"action": "goto", "name": "打开页面", "params": {"url": "https://example.com?token=secret"}}],
        network_events=[{"type": "response", "url": "https://example.com?token=secret", "status": 200}],
    )

    asyncio.run(session._persist_artifacts())

    assert set(session.artifacts) == {"trace", "har", "report"}
    assert len(uploaded) == 3
    assert "secret" not in har_path.read_text(encoding="utf-8")
    report_payload = json.loads(report_path.read_text(encoding="utf-8"))
    assert report_payload["start_url"] == "https://example.com?token=%2A%2A%2A"
    assert "secret" not in json.dumps(report_payload)


def test_recording_script_does_not_duplicate_checkbox_or_radio_changes():
    change_handler = _RECORDING_SCRIPT.split("document.addEventListener('change'", 1)[1]

    assert "target instanceof HTMLSelectElement" in change_handler
    assert "type: 'click'" not in change_handler


def test_recording_manager_prunes_finished_sessions(monkeypatch):
    import app.api.v1.web_recordings as web_recordings

    manager = WebRecordingManager()
    manager.retention_seconds = 300
    manager.sessions = {
        "expired": WebRecordingSession(
            session_id="expired",
            owner_id=1,
            start_url="https://example.com",
            viewport_width=1280,
            viewport_height=720,
            status="stopped",
            finished_at=100,
        ),
        "active": WebRecordingSession(
            session_id="active",
            owner_id=1,
            start_url="https://example.com",
            viewport_width=1280,
            viewport_height=720,
            status="recording",
        ),
    }
    monkeypatch.setattr(web_recordings.time, "monotonic", lambda: 500)

    manager._prune_finished()

    assert set(manager.sessions) == {"active"}


def test_recording_snapshot_exposes_current_page_url_and_screenshot():
    class _Page:
        url = "https://example.com/checkout"

        async def screenshot(self, type="png"):
            assert type == "png"
            return b"png-bytes"

    session = WebRecordingSession(
        session_id="screenshot-session",
        owner_id=1,
        start_url="https://example.com",
        viewport_width=1280,
        viewport_height=720,
        status="recording",
        page=_Page(),
    )

    assert session.snapshot()["current_url"] == "https://example.com/checkout"
    assert asyncio.run(session.screenshot()) == b"png-bytes"


def test_recording_session_blocks_private_navigation_and_exposes_evidence():
    class _Route:
        request = SimpleNamespace(url="http://127.0.0.1:8000/admin", resource_type="document")

        def __init__(self):
            self.aborted_with = None

        async def abort(self, error_code):
            self.aborted_with = error_code

        async def continue_(self):
            raise AssertionError("private request must not continue")

    session = WebRecordingSession(
        session_id="guard-session",
        owner_id=1,
        start_url="https://example.com",
        viewport_width=1280,
        viewport_height=720,
        status="recording",
    )
    route = _Route()

    assert asyncio.run(session._guard_route(route)) is False
    assert route.aborted_with == "blockedbyclient"
    assert session.snapshot()["blocked_requests"][0]["resource_type"] == "document"


def test_recording_session_can_persist_assets_and_link_steps():
    class _ScalarResult:
        def all(self):
            return []

    class _Rows:
        def scalars(self):
            return _ScalarResult()

    class _DB:
        def __init__(self):
            self.items = []
            self.commits = 0

        async def execute(self, _query):
            return _Rows()

        def add(self, item):
            item.id = len(self.items) + 1
            self.items.append(item)

        async def flush(self):
            return None

        async def commit(self):
            self.commits += 1

    session = WebRecordingSession(
        session_id="asset-session",
        owner_id=1,
        project_id=7,
        start_url="https://example.com/login",
        viewport_width=1280,
        viewport_height=720,
        status="stopped",
        steps=[
            {"action": "fill", "name": "输入用户名", "params": {"selector": "#username", "value": "alice"}},
            {"action": "click", "name": "点击登录", "params": {"selector": "#login"}},
        ],
    )
    db = _DB()

    asyncio.run(_persist_recorded_assets(db, session))

    assert len(db.items) == 2
    assert all(isinstance(item, WebElementAsset) for item in db.items)
    assert session.asset_ids == [1, 2]
    assert session.steps[0]["params"]["element_asset_id"] == 1
    assert session.steps[1]["params"]["element_asset_id"] == 2
    assert db.commits == 1


def test_recording_session_starts_browser_collects_navigation_and_stops(monkeypatch):
    import app.api.v1.web_recordings as web_recordings

    class _Page:
        url = "about:blank"
        bindings = []
        scripts = []
        handlers = {}

        async def expose_binding(self, name, handler):
            self.bindings.append((name, handler))

        async def add_init_script(self, script):
            self.scripts.append(script)

        def on(self, event, handler):
            self.handlers[event] = handler

        async def goto(self, url, **_kwargs):
            self.url = url

        async def screenshot(self, **_kwargs):
            return b"recording-png"

    class _Context:
        def __init__(self):
            self.routes = []
            self.page = _Page()
            self.closed = False

        async def route(self, pattern, handler):
            self.routes.append((pattern, handler))

        async def new_page(self):
            return self.page

        async def close(self):
            self.closed = True

    class _Browser:
        def __init__(self):
            self.context = _Context()
            self.closed = False

        async def new_context(self, **_kwargs):
            return self.context

        async def close(self):
            self.closed = True

    class _Launcher:
        def __init__(self):
            self.browser = _Browser()
            self.launch_args = None

        async def launch(self, **kwargs):
            self.launch_args = kwargs
            return self.browser

    class _Playwright:
        def __init__(self):
            self.chromium = _Launcher()
            self.firefox = _Launcher()
            self.webkit = _Launcher()
            self.stopped = False

        async def stop(self):
            self.stopped = True

    class _Factory:
        def __init__(self):
            self.playwright = _Playwright()

        async def start(self):
            return self.playwright

    factory = _Factory()
    monkeypatch.setattr(web_recordings, "async_playwright", lambda: factory)
    monkeypatch.setattr(web_recordings.settings, "WEB_RECORDER_DISPLAY", ":99")
    session = WebRecordingSession(
        session_id="start-session",
        owner_id=1,
        project_id=2,
        start_url="https://example.com/login",
        viewport_width=1440,
        viewport_height=900,
    )

    asyncio.run(session.start())

    assert session.status == "recording"
    assert session.steps[0]["action"] == "goto"
    assert session.snapshot()["browser"] == "chromium"
    assert factory.playwright.chromium.launch_args["headless"] is False
    assert factory.playwright.chromium.browser.context.routes[0][0] == "**/*"
    assert asyncio.run(session.screenshot()) == b"recording-png"

    asyncio.run(session.stop())
    assert session.status == "stopped"
    assert session.context is None
    assert session.browser is None
    assert session.playwright is None

    for browser_name in ("firefox", "webkit"):
        session = WebRecordingSession(
            session_id=f"{browser_name}-session",
            owner_id=1,
            project_id=2,
            start_url="https://example.com/login",
            viewport_width=1440,
            viewport_height=900,
            browser_name=browser_name,
        )
        asyncio.run(session.start())
        assert session.snapshot()["browser"] == browser_name
        assert getattr(factory.playwright, browser_name).launch_args["headless"] is False
        asyncio.run(session.stop())

    monkeypatch.setattr(web_recordings.settings, "WEB_RECORDER_MODE", "worker")
    session = WebRecordingSession(
        session_id="webkit-worker-session",
        owner_id=1,
        project_id=2,
        start_url="https://example.com/login",
        viewport_width=1440,
        viewport_height=900,
        browser_name="webkit",
    )
    monkeypatch.setattr(web_recordings.sys, "platform", "linux")
    asyncio.run(session.start())
    assert factory.playwright.webkit.launch_args["headless"] is True
    asyncio.run(session.stop())


def test_recording_session_start_failure_closes_partial_resources(monkeypatch):
    import app.api.v1.web_recordings as web_recordings

    class _Factory:
        async def start(self):
            raise RuntimeError("browser unavailable")

    monkeypatch.setattr(web_recordings, "async_playwright", lambda: _Factory())
    session = WebRecordingSession(
        session_id="failed-session",
        owner_id=1,
        start_url="https://example.com",
        viewport_width=1280,
        viewport_height=720,
    )

    with pytest.raises(RuntimeError, match="browser unavailable"):
        asyncio.run(session.start())

    assert session.status == "error"
    assert session.error == "browser unavailable"
    assert session.finished_at is not None


def test_recording_manager_rejects_duplicate_owner_and_handles_cleanup(monkeypatch):
    async def _start(session):
        session.status = "recording"

    async def _stop(session):
        session.status = "stopped"

    monkeypatch.setattr(WebRecordingSession, "start", _start)
    monkeypatch.setattr(WebRecordingSession, "stop", _stop)
    manager = WebRecordingManager()
    payload = WebRecordingStart(start_url="https://example.com", project_id=1)

    session = asyncio.run(manager.start(payload, owner_id=7))
    assert manager.get(session.session_id, owner_id=7) is session
    with pytest.raises(HTTPException) as duplicate:
        asyncio.run(manager.start(payload, owner_id=7))
    assert duplicate.value.status_code == 409
    with pytest.raises(HTTPException) as missing:
        manager.get(session.session_id, owner_id=8)
    assert missing.value.status_code == 404

    other = WebRecordingSession(
        session_id="other-session",
        owner_id=9,
        start_url="https://example.com",
        viewport_width=1280,
        viewport_height=720,
        status="recording",
    )
    manager.sessions[other.session_id] = other
    asyncio.run(manager.close_all())
    assert manager.sessions == {}
    assert other.status == "stopped"


def test_persist_assets_handles_empty_steps_existing_names_and_conflicts():
    class _Rows:
        def __init__(self, names):
            self.names = names

        def scalars(self):
            return self

        def all(self):
            return self.names

    class _DB:
        def __init__(self, names=None, fail=False):
            self.names = names or []
            self.items = []
            self.commits = 0
            self.rollbacks = 0
            self.fail = fail

        async def execute(self, _query):
            return _Rows(self.names)

        def add(self, item):
            item.id = len(self.items) + 1
            self.items.append(item)

        async def flush(self):
            if self.fail:
                from sqlalchemy.exc import IntegrityError

                raise IntegrityError("insert", {}, RuntimeError("duplicate"))

        async def rollback(self):
            self.rollbacks += 1

        async def commit(self):
            self.commits += 1

    empty = WebRecordingSession(
        session_id="empty-assets",
        owner_id=1,
        project_id=1,
        start_url="https://example.com",
        viewport_width=1280,
        viewport_height=720,
        steps=[{"action": "goto", "params": {"url": "https://example.com"}}],
    )
    empty_db = _DB()
    asyncio.run(_persist_recorded_assets(empty_db, empty))
    assert empty.assets_persisted is True
    assert empty_db.items == []

    session = WebRecordingSession(
        session_id="existing-assets",
        owner_id=1,
        project_id=1,
        start_url="https://example.com",
        viewport_width=1280,
        viewport_height=720,
        steps=[{"action": "click", "params": {"selector": "#save"}}],
    )
    db = _DB(names=["录制元素_1"])
    asyncio.run(_persist_recorded_assets(db, session))
    assert db.items[0].name == "录制元素_1_2"
    assert db.commits == 1

    conflict = WebRecordingSession(
        session_id="conflict-assets",
        owner_id=1,
        project_id=1,
        start_url="https://example.com",
        viewport_width=1280,
        viewport_height=720,
        steps=[{"action": "click", "params": {"selector": "#save"}}],
    )
    conflict_db = _DB(fail=True)
    asyncio.run(_persist_recorded_assets(conflict_db, conflict))
    assert conflict.error and conflict_db.rollbacks == 1
    assert conflict.assets_persisted is False


def test_recording_routes_validate_start_screenshot_and_stop(monkeypatch):
    import app.api.v1.web_recordings as web_recordings

    user = SimpleNamespace(id=5)
    project = SimpleNamespace(id=1)

    class _DB:
        async def get(self, _model, _project_id):
            return project

    async def _allow_access(*_args, **_kwargs):
        return None

    session = WebRecordingSession(
        session_id="route-session",
        owner_id=user.id,
        project_id=1,
        start_url="https://example.com",
        viewport_width=1280,
        viewport_height=720,
        status="recording",
    )
    monkeypatch.setattr(web_recordings, "assert_project_access", _allow_access)
    monkeypatch.setattr(web_recordings, "validate_public_http_url", lambda url: url + "/checked")
    # 单元测试覆盖本地路由 manager；真实 Worker 模式由独立 transport 测试和
    # Web Worker smoke 验收覆盖，不能让开发机 .env 决定该单测走哪条分支。
    monkeypatch.setattr(web_recordings.settings, "WEB_RECORDER_MODE", "local")

    async def _start(_payload, _owner_id):
        return session

    monkeypatch.setattr(web_recordings.manager, "start", _start)
    payload = WebRecordingStart(start_url="https://example.com", project_id=1)
    result = asyncio.run(web_recordings.start_recording(payload, _DB(), user))
    assert result["id"] == "route-session"
    assert payload.start_url.endswith("/checked")

    def _reject(_url):
        raise ValueError("private address")

    monkeypatch.setattr(web_recordings, "validate_public_http_url", _reject)
    with pytest.raises(HTTPException) as invalid:
        asyncio.run(web_recordings.start_recording(payload, _DB(), user))
    assert invalid.value.status_code == 400

    web_recordings.manager.sessions[session.session_id] = session
    response = asyncio.run(web_recordings.get_recording(session.session_id, user))
    assert response["id"] == "route-session"

    async def _screenshot():
        return b"png"

    session.screenshot = _screenshot
    screenshot = asyncio.run(web_recordings.capture_recording_screenshot(session.session_id, user))
    assert screenshot.body == b"png" and screenshot.media_type == "image/png"

    async def _bad_screenshot():
        raise RuntimeError("not ready")

    session.screenshot = _bad_screenshot
    with pytest.raises(HTTPException) as screenshot_error:
        asyncio.run(web_recordings.capture_recording_screenshot(session.session_id, user))
    assert screenshot_error.value.status_code == 409

    persisted = False

    async def _persist(_db, _session):
        nonlocal persisted
        persisted = True

    monkeypatch.setattr(web_recordings, "_persist_recorded_assets", _persist)
    stopped = asyncio.run(web_recordings.stop_recording(session.session_id, _DB(), user))
    assert stopped["id"] == "route-session" and persisted is True


def test_recording_route_reports_missing_project(monkeypatch):
    import app.api.v1.web_recordings as web_recordings

    class _DB:
        async def get(self, _model, _project_id):
            return None

    async def _allow_access(*_args, **_kwargs):
        return None

    monkeypatch.setattr(web_recordings, "assert_project_access", _allow_access)
    monkeypatch.setattr(web_recordings, "validate_public_http_url", lambda url: url)
    payload = WebRecordingStart(start_url="https://example.com", project_id=1)

    with pytest.raises(HTTPException) as missing:
        asyncio.run(web_recordings.start_recording(payload, _DB(), SimpleNamespace(id=1)))
    assert missing.value.status_code == 404


def test_recording_routes_delegate_to_remote_worker_mode(monkeypatch):
    import app.api.v1.web_recordings as web_recordings

    class _DB:
        async def get(self, _model, _project_id):
            return SimpleNamespace(id=1)

    user = SimpleNamespace(id=5)
    payload = WebRecordingStart(start_url="https://example.com", project_id=1)
    monkeypatch.setattr(web_recordings.settings, "WEB_RECORDER_MODE", "worker")
    monkeypatch.setattr(web_recordings, "assert_project_access", lambda *_args, **_kwargs: asyncio.sleep(0))
    monkeypatch.setattr(web_recordings, "validate_public_http_url", lambda url: url)

    async def remote_start(_payload, owner_id):
        assert owner_id == user.id
        return {"id": "remote-1", "status": "recording", "project_id": 1, "steps": []}

    async def remote_get(session_id, owner_id):
        assert (session_id, owner_id) == ("remote-1", user.id)
        return {"id": session_id, "status": "recording", "project_id": 1, "steps": []}

    async def remote_screenshot(session_id, owner_id):
        assert (session_id, owner_id) == ("remote-1", user.id)
        return b"remote-png"

    async def remote_stop(session_id, owner_id):
        assert (session_id, owner_id) == ("remote-1", user.id)
        return {"id": session_id, "status": "stopped", "project_id": 1, "steps": []}

    monkeypatch.setattr(web_recordings.remote_manager, "start", remote_start)
    monkeypatch.setattr(web_recordings.remote_manager, "get", remote_get)
    monkeypatch.setattr(web_recordings.remote_manager, "screenshot", remote_screenshot)
    monkeypatch.setattr(web_recordings.remote_manager, "stop", remote_stop)
    persisted = []

    async def persist(_db, session):
        persisted.append(session.session_id)

    monkeypatch.setattr(web_recordings, "_persist_recorded_assets", persist)

    assert asyncio.run(web_recordings.start_recording(payload, _DB(), user))["id"] == "remote-1"
    assert asyncio.run(web_recordings.get_recording("remote-1", user))["status"] == "recording"
    assert asyncio.run(web_recordings.capture_recording_screenshot("remote-1", user)).body == b"remote-png"
    assert asyncio.run(web_recordings.stop_recording("remote-1", _DB(), user))["status"] == "stopped"
    assert persisted == ["remote-1"]


def test_recording_worker_status_reports_capacity_without_process_details(monkeypatch):
    import app.api.v1.web_recordings as web_recordings

    monkeypatch.setattr(web_recordings.settings, "WEB_RECORDER_MODE", "worker")

    async def list_workers():
        return [
            {
                "worker_id": "windows-worker",
                "active_sessions": 1,
                "capacity": 2,
                "updated_at": "1700000000",
                "hostname": "private-host",
                "pid": 1234,
            },
            {"worker_id": "full-worker", "active_sessions": 2, "capacity": 2},
        ]

    monkeypatch.setattr(web_recordings, "list_recording_workers", list_workers)
    result = asyncio.run(web_recordings.get_recording_workers(SimpleNamespace(id=1)))

    assert result["mode"] == "worker"
    assert result["ready"] is True
    assert result["registered_count"] == 2
    assert result["available_count"] == 1
    assert result["workers"][0]["worker_id"].startswith("worker-")
    assert result["workers"][1]["worker_id"].startswith("worker-")
    assert result["workers"][0]["worker_id"] != "windows-worker"
    assert result["workers"][1]["worker_id"] != "full-worker"
    assert result["workers"][0]["active_sessions"] == 1
    assert result["workers"][0]["capacity"] == 2
    assert result["workers"][0]["available"] is True
    assert result["workers"][0]["updated_at"] == 1700000000.0
    assert result["workers"][1]["active_sessions"] == 2
    assert result["workers"][1]["capacity"] == 2
    assert result["workers"][1]["available"] is False
    assert result["workers"][1]["updated_at"] is None
    assert "hostname" not in result["workers"][0]
    assert "pid" not in result["workers"][0]


def test_recording_worker_status_is_ready_in_local_mode(monkeypatch):
    import app.api.v1.web_recordings as web_recordings

    monkeypatch.setattr(web_recordings.settings, "WEB_RECORDER_MODE", "local")
    result = asyncio.run(web_recordings.get_recording_workers(SimpleNamespace(id=1)))

    assert result == {
        "mode": "local",
        "ready": True,
        "workers": [],
        "registered_count": 0,
        "available_count": 0,
    }
