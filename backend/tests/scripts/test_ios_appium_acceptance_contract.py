"""Behavior and safety checks for the macOS/iOS Appium acceptance command."""

from __future__ import annotations

import base64
import importlib.util
import json
from pathlib import Path
import sys

import pytest


ROOT = Path(__file__).resolve().parents[3]


def _load_script():
    path = ROOT / "scripts" / "ios-appium-acceptance.py"
    spec = importlib.util.spec_from_file_location("ios_appium_acceptance", path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_appium_url_rejects_credentials_and_query_strings():
    script = _load_script()

    with pytest.raises(script.AcceptanceError):
        script._safe_url("https://user:password@appium.example.test:4723")
    with pytest.raises(script.AcceptanceError):
        script._safe_url("https://appium.example.test:4723/wd/hub?token=secret")


def test_status_only_acceptance_writes_a_passed_report(monkeypatch, tmp_path):
    script = _load_script()

    class _Response:
        status = 200

        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return False

        def read(self):
            return b'{"value":{"ready":true,"message":"ready"}}'

    calls: list[str] = []

    def fake_urlopen(request, timeout):
        del timeout
        calls.append(request.full_url)
        return _Response()

    monkeypatch.setattr(script, "urlopen", fake_urlopen)
    report_path = tmp_path / "ios.json"

    assert script.main(["--appium-url", "http://appium.example.test:4723/wd/hub", "--report", str(report_path)]) == 0

    report = json.loads(report_path.read_text(encoding="utf-8"))
    assert report["status"] == "passed"
    assert report["session_smoke"] is False
    assert calls == ["http://appium.example.test:4723/wd/hub/status"]


def test_session_smoke_creates_cleans_session_and_records_screenshot(monkeypatch, tmp_path):
    script = _load_script()
    screenshot = base64.b64encode(b"png-bytes").decode("ascii")

    class _Response:
        status = 200

        def __init__(self, body):
            self.body = body

        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return False

        def read(self):
            return json.dumps(self.body).encode("utf-8")

    calls: list[tuple[str, str]] = []

    def fake_urlopen(request, timeout):
        del timeout
        calls.append((request.method, request.full_url))
        if request.method == "GET" and request.full_url.endswith("/status"):
            return _Response({"value": {"ready": True}})
        if request.method == "POST" and request.full_url.endswith("/session"):
            return _Response({"value": {"sessionId": "session-1"}})
        if request.method == "GET" and request.full_url.endswith("/session/session-1/screenshot"):
            return _Response({"value": screenshot})
        if request.method == "DELETE" and request.full_url.endswith("/session/session-1"):
            return _Response({"value": {}})
        raise AssertionError((request.method, request.full_url))

    monkeypatch.setattr(script, "urlopen", fake_urlopen)
    report_path = tmp_path / "ios-session.json"
    artifact_dir = tmp_path / "artifacts"

    assert (
        script.main(
            [
                "--appium-url",
                "http://appium.example.test:4723",
                "--udid",
                "simulator-1",
                "--session-smoke",
                "--artifact-dir",
                str(artifact_dir),
                "--report",
                str(report_path),
            ]
        )
        == 0
    )

    report = json.loads(report_path.read_text(encoding="utf-8"))
    assert report["status"] == "passed"
    assert report["artifacts"][0]["name"] == "screenshot.png"
    assert (artifact_dir / "screenshot.png").read_bytes() == b"png-bytes"
    assert any(method == "DELETE" and url.endswith("/session/session-1") for method, url in calls)


def test_session_smoke_records_video_around_steps_and_hashes_artifacts(monkeypatch, tmp_path):
    script = _load_script()
    screenshot = base64.b64encode(b"png-bytes").decode("ascii")
    recording = base64.b64encode(b"mp4-bytes").decode("ascii")

    class _Response:
        status = 200

        def __init__(self, body):
            self.body = body

        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return False

        def read(self):
            return json.dumps(self.body).encode("utf-8")

    calls: list[tuple[str, str]] = []

    def fake_urlopen(request, timeout):
        del timeout
        calls.append((request.method, request.full_url))
        if request.method == "GET" and request.full_url.endswith("/status"):
            return _Response({"value": {"ready": True}})
        if request.method == "POST" and request.full_url.endswith("/session"):
            return _Response({"value": {"sessionId": "session-1"}})
        if request.method == "POST" and request.full_url.endswith("/appium/start_recording_screen"):
            return _Response({"value": {}})
        if request.method == "GET" and request.full_url.endswith("/screenshot"):
            return _Response({"value": screenshot})
        if request.method == "POST" and request.full_url.endswith("/appium/stop_recording_screen"):
            return _Response({"value": recording})
        if request.method == "DELETE" and request.full_url.endswith("/session/session-1"):
            return _Response({"value": {}})
        raise AssertionError((request.method, request.full_url))

    monkeypatch.setattr(script, "urlopen", fake_urlopen)
    report_path = tmp_path / "ios-video.json"
    artifact_dir = tmp_path / "artifacts"

    assert (
        script.main(
            [
                "--appium-url",
                "http://appium.example.test:4723",
                "--udid",
                "simulator-1",
                "--session-smoke",
                "--artifact-dir",
                str(artifact_dir),
                "--record-video",
                "--report",
                str(report_path),
            ]
        )
        == 0
    )

    report = json.loads(report_path.read_text(encoding="utf-8"))
    assert {item["name"] for item in report["artifacts"]} == {"screenshot.png", "screen-recording.mp4"}
    assert (artifact_dir / "screen-recording.mp4").read_bytes() == b"mp4-bytes"
    start_index = next(index for index, call in enumerate(calls) if call[1].endswith("/start_recording_screen"))
    stop_index = next(index for index, call in enumerate(calls) if call[1].endswith("/stop_recording_screen"))
    delete_index = next(index for index, call in enumerate(calls) if call[0] == "DELETE")
    assert start_index < stop_index < delete_index


def test_ios_appium_runbook_matches_acceptance_script():
    runbook = (ROOT / "docs" / "ios-appium-acceptance.md").read_text(encoding="utf-8")

    assert "scripts/ios-appium-acceptance.py" in runbook
    assert "--session-smoke" in runbook
    assert "--record-video" in runbook
    assert "--collect-syslog" in runbook
    assert "Windows/Linux" in runbook


def test_acceptance_report_does_not_include_input_text_or_remote_app_query(monkeypatch, tmp_path):
    script = _load_script()

    class _Response:
        status = 200

        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return False

        def read(self):
            return b'{"value":{"ready":true}}'

    monkeypatch.setattr(script, "urlopen", lambda *_args, **_kwargs: _Response())
    report_path = tmp_path / "safe.json"
    assert script.main(["--appium-url", "http://appium.example.test:4723", "--report", str(report_path)]) == 0
    content = report_path.read_text(encoding="utf-8")
    assert "password" not in content
    assert "access_token" not in content
