"""Contract tests for the notification channel acceptance command."""

from __future__ import annotations

import importlib.util
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[3]
SCRIPT = ROOT / "scripts" / "notification-channel-smoke.py"


def _module():
    spec = importlib.util.spec_from_file_location("notification_channel_smoke", SCRIPT)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_notification_smoke_redacts_urls_and_credentials_from_report_inputs():
    module = _module()
    assert module._redact_url("https://user:password@example.test/api?token=secret") == (
        "https://<redacted>@example.test/api?<redacted>"
    )
    assert "secret" not in module._safe_error("token=secret")
    assert "secret" not in module._safe_error("password=secret")
    safe = module._safe_error("request failed: https://qyapi.weixin.qq.com/cgi-bin/webhook/send?key=wechat-secret")
    assert "wechat-secret" not in safe
    assert "?key=<redacted>" in safe


def test_notification_smoke_acceptance_uses_environment_credentials_only():
    source = SCRIPT.read_text(encoding="utf-8")
    assert "ATP_TOKEN" in source
    assert "ATP_USERNAME" in source
    assert "ATP_PASSWORD" in source
    assert "--token" not in source
    assert "--password" not in source
    assert "/api/v1/notifications/{args.config_id}/test" in source
    assert "/api/v1/notifications/deliveries?" in source


def test_notification_smoke_report_does_not_dump_environment():
    source = SCRIPT.read_text(encoding="utf-8")
    assert "os.environ" in source
    assert "os.environ.items" not in source
    assert "os.environ.copy" not in source
