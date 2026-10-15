"""Unit tests for T1.3 IPA asset parsing and iOS low-code step execution.

Tests:
1. extract_ipa_metadata reads Bundle ID, version, app name, minimum OS, and supported devices from Info.plist
2. extract_ipa_metadata gracefully handles corrupted archives and missing Info.plist
3. IosAppiumClient lowcode actions (tap, swipe, wait, assert_element)
4. WDA session crash detection during step execution
"""

from __future__ import annotations

import io
import plistlib
import zipfile
from typing import Any
from unittest.mock import AsyncMock
import pytest

from app.models.bootstrap import load_all_models
from app.services.ipa_parser import extract_ipa_metadata
from app.services.ios_wda_session_healer import is_wda_session_crash
from app.worker.executors.ios_executor import IosAppiumClient, _touch_actions

load_all_models()


def _create_mock_ipa(plist_content: dict) -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
        plist_bytes = plistlib.dumps(plist_content)
        z.writestr("Payload/TestApp.app/Info.plist", plist_bytes)
        z.writestr("Payload/TestApp.app/PkgInfo", b"APPL????")
    return buf.getvalue()


def test_extract_ipa_metadata_success():
    plist_data = {
        "CFBundleIdentifier": "com.atp.mobile.test",
        "CFBundleShortVersionString": "1.4.0",
        "CFBundleVersion": "10401",
        "CFBundleDisplayName": "ATP 移动助手",
        "MinimumOSVersion": "15.0",
        "UIDeviceFamily": [1, 2],
    }
    ipa_bytes = _create_mock_ipa(plist_data)
    meta = extract_ipa_metadata(ipa_bytes)

    assert meta["bundle_id"] == "com.atp.mobile.test"
    assert meta["version_name"] == "1.4.0"
    assert meta["build_version"] == "10401"
    assert meta["app_name"] == "ATP 移动助手"
    assert meta["min_os_version"] == "15.0"
    assert "iPhone" in meta["supported_devices"]
    assert "iPad" in meta["supported_devices"]


def test_extract_ipa_metadata_corrupted_archive_returns_empty():
    assert extract_ipa_metadata(b"not a valid zip file") == {}

    # Valid zip but missing Payload/*.app/Info.plist
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as z:
        z.writestr("readme.txt", "hello")
    assert extract_ipa_metadata(buf.getvalue()) == {}


def test_ios_touch_actions():
    tap_actions = _touch_actions({"x": 100, "y": 200}, "tap")
    assert tap_actions["type"] == "pointer"
    assert tap_actions["actions"][0]["x"] == 100
    assert tap_actions["actions"][0]["y"] == 200

    swipe_actions = _touch_actions({"x": 50, "y": 300, "to_x": 50, "to_y": 100, "duration_ms": 400}, "swipe")
    assert len(swipe_actions["actions"]) == 4
    assert swipe_actions["actions"][2]["x"] == 50
    assert swipe_actions["actions"][2]["y"] == 100
    assert swipe_actions["actions"][2]["duration"] == 400


@pytest.mark.asyncio
async def test_appium_client_dispatches_tap_and_swipe():
    mock_requests: list[tuple[str, str, dict | None]] = []

    class _MockHttp:
        async def request(self, method: str, url: str, json: dict | None = None):
            mock_requests.append((method, url, json))
            return AsyncMock(status_code=200, json=lambda: {"value": {}})

        async def aclose(self):
            return None

    mock_http: Any = _MockHttp()
    client = IosAppiumClient("http://mac-worker:4723", http_client=mock_http)
    client.session_id = "test-session-1"

    tap_res = await client.execute_step("tap", {"x": 120, "y": 240})
    assert tap_res["success"] is True

    swipe_res = await client.execute_step("swipe", {"x": 10, "y": 50, "to_x": 10, "to_y": 200})
    assert swipe_res["success"] is True

    wait_res = await client.execute_step("wait", {"seconds": 0.01})
    assert wait_res["success"] is True
    assert wait_res["wait_seconds"] == 0.01

    assert len(mock_requests) >= 2
    assert any("/actions" in r[1] for r in mock_requests)


def test_wda_session_crash_detection():
    assert is_wda_session_crash("WebDriverException: A session is either terminated or not started") is True
    assert is_wda_session_crash("AppiumProtocolError: WDA unresponsive during swipe") is True
    assert is_wda_session_crash("RuntimeError: normal assertion failed") is False
