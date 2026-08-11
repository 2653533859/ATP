import asyncio

import pytest

from app.api.v1.web_recordings import (
    _RECORDING_SCRIPT,
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
        WebRecordingStart(start_url="file:///tmp/page.html")


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
