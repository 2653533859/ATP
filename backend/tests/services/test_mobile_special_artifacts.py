"""Tests for bounded Android special-run artifact capture."""

import asyncio
import types

from app.models.mobile_special import MobileRunArtifact
from app.services import mobile_special_artifacts as artifacts
from app.services.mobile_special_events import MobileRunEventRecorder

from app.models import load_all_models


load_all_models()


class _FakeDB:
    def __init__(self):
        self.added = []
        self.commits = 0

    def add(self, value):
        self.added.append(value)

    async def commit(self):
        self.commits += 1


def test_capture_mobile_run_artifacts_persists_logcat_and_screenshot(monkeypatch):
    db = _FakeDB()
    run = types.SimpleNamespace(
        id=12,
        device_serial="emulator-5554",
        config_snapshot={"capture_device_logs": True, "capture_screenshot": True},
        summary_json={"status": "completed"},
    )
    uploads = []

    def fake_run(command, **_kwargs):
        if "screencap" in command:
            return types.SimpleNamespace(returncode=0, stdout=b"\x89PNG\r\nimage", stderr=b"")
        return types.SimpleNamespace(returncode=0, stdout=b"01-01 00:00:00.000 I/Test: ok", stderr=b"")

    monkeypatch.setattr(artifacts.subprocess, "run", fake_run)
    monkeypatch.setattr(
        artifacts,
        "upload_bytes",
        lambda name, data, content_type: uploads.append((name, data, content_type)),
    )

    result = asyncio.run(artifacts.capture_mobile_run_artifacts(db, run, MobileRunEventRecorder(db, run.id)))

    assert result["logcat"]["saved"] is True
    assert result["screenshot"]["saved"] is True
    assert len([item for item in db.added if isinstance(item, MobileRunArtifact)]) == 2
    assert {item[2] for item in uploads} == {"text/plain; charset=utf-8", "image/png"}
    assert run.summary_json["android_artifacts"]["screenshot"]["file_name"] == "run_12_final.png"
    assert db.commits == 1


def test_capture_mobile_run_artifacts_keeps_run_usable_when_adb_fails(monkeypatch):
    db = _FakeDB()
    run = types.SimpleNamespace(
        id=13,
        device_serial="emulator-5554",
        config_snapshot={"capture_device_logs": True, "capture_screenshot": True},
        summary_json={},
    )

    def broken_run(_command, **_kwargs):
        raise FileNotFoundError("adb")

    monkeypatch.setattr(artifacts.subprocess, "run", broken_run)

    result = asyncio.run(artifacts.capture_mobile_run_artifacts(db, run, MobileRunEventRecorder(db, run.id)))

    assert result["logcat"]["saved"] is False
    assert result["screenshot"]["saved"] is False
    assert not [item for item in db.added if isinstance(item, MobileRunArtifact)]
    assert run.summary_json["android_artifacts"]["logcat"]["error"] == "adb 命令未找到"
    assert db.commits == 1


def test_capture_mobile_run_artifacts_redacts_upload_error(monkeypatch):
    db = _FakeDB()
    run = types.SimpleNamespace(
        id=14,
        device_serial="emulator-5554",
        config_snapshot={"capture_device_logs": True},
        summary_json={},
    )

    monkeypatch.setattr(
        artifacts.subprocess,
        "run",
        lambda _command, **_kwargs: types.SimpleNamespace(returncode=0, stdout=b"log", stderr=b""),
    )

    def broken_upload(*_args):
        raise RuntimeError("upload failed token=secret-value")

    monkeypatch.setattr(artifacts, "upload_bytes", broken_upload)

    result = asyncio.run(artifacts.capture_mobile_run_artifacts(db, run, MobileRunEventRecorder(db, run.id)))

    assert result["logcat"]["saved"] is False
    assert "secret-value" not in result["logcat"]["error"]
    assert "[REDACTED]" in result["logcat"]["error"]
