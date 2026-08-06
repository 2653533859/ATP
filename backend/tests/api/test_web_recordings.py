import pytest

from app.api.v1.web_recordings import (
    _RECORDING_SCRIPT,
    WebRecordingManager,
    WebRecordingSession,
    WebRecordingStart,
)


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
