"""Contract tests for the Web Recording Worker acceptance command."""

from __future__ import annotations

import importlib.util
from pathlib import Path
import sys

import pytest


ROOT = Path(__file__).resolve().parents[3]
SCRIPT = ROOT / "scripts" / "web-recording-worker-smoke.py"


def _module():
    spec = importlib.util.spec_from_file_location("web_recording_worker_smoke", SCRIPT)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_worker_smoke_redacts_urls_and_sensitive_error_text():
    module = _module()
    assert module._redact_url("https://user:password@example.test/api?token=secret") == (
        "https://<redacted>@example.test/api?<redacted>"
    )
    safe = module._safe_error("failed https://example.test/path?token=secret password=secret")
    assert "secret" not in safe
    assert "?token=secret" not in safe
    assert "?<redacted>" in safe


def test_worker_smoke_requires_explicit_real_recording(monkeypatch):
    module = _module()
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "web-recording-worker-smoke.py",
            "--api-base-url",
            "https://example.test",
            "--project-id",
            "7",
            "--screenshot",
        ],
    )
    with pytest.raises(SystemExit):
        module._parse_args()


def test_worker_smoke_uses_environment_credentials_and_worker_routes():
    source = SCRIPT.read_text(encoding="utf-8")
    assert "ATP_TOKEN" in source
    assert "ATP_USERNAME" in source
    assert "ATP_PASSWORD" in source
    assert "--token" not in source
    assert "--password" not in source
    assert "/api/v1/web-recordings/workers" in source
    assert "/api/v1/web-recordings/{session_id}/screenshot" in source
    assert 'headers.get("content-type"' in source
    assert "--run-recording" in source


def test_worker_smoke_normalizes_response_header_names():
    module = _module()

    class _Response:
        headers = {"Content-Type": "image/png"}

        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return False

        def read(self):
            return b"png"

    class _Opener:
        def open(self, *_args, **_kwargs):
            return _Response()

    client = module.ApiClient("https://example.test", token=None, timeout=1)
    client._opener = _Opener()
    headers, body = client.request_raw("POST", "/api/v1/web-recordings/session/screenshot")

    assert headers == {"content-type": "image/png"}
    assert body == b"png"
