"""Behavior tests for the Appium protocol boundary."""

import asyncio

import pytest

from app.worker.executors.ios_executor import IosAppiumClient, _render_params, _touch_actions


class _Response:
    def __init__(self, status_code: int, payload):
        self.status_code = status_code
        self._payload = payload

    def json(self):
        return self._payload


class _FakeHttp:
    def __init__(self):
        self.requests = []

    async def request(self, method, url, json=None):
        self.requests.append((method, url, json))
        if url.endswith("/session"):
            return _Response(200, {"value": {"sessionId": "ios-session"}})
        if url.endswith("/element"):
            return _Response(200, {"value": {"element-6066-11e4-a52e-4f735466cecf": "element-1"}})
        if url.endswith("/source"):
            return _Response(200, {"value": '<XCUIElementTypeStaticText name="登录成功" />'})
        if url.endswith("/screenshot"):
            return _Response(200, {"value": "c2NyZWVu"})
        return _Response(200, {"value": {}})

    async def aclose(self):
        return None


def test_appium_client_creates_session_and_dispatches_lowcode_actions():
    fake = _FakeHttp()
    client = IosAppiumClient("http://mac-worker:4723", http_client=fake)

    async def run():
        await client.start_session(
            udid="device-1",
            device_name="iPhone 15",
            platform_version="17.5",
            bundle_id="com.example.app",
            app=None,
        )
        clicked = await client.execute_step("click", {"strategy": "accessibility_id", "value": "登录"})
        entered = await client.execute_step("input", {"strategy": "id", "value": "email", "text": "user@example.com"})
        asserted = await client.execute_step("assert_text", {"text": "登录成功"})
        screenshot = await client.screenshot()
        await client.quit()
        return clicked, entered, asserted, screenshot

    clicked, entered, asserted, screenshot = asyncio.run(run())
    assert clicked == {"success": True, "element_id": "element-1"}
    assert entered == {"success": True, "element_id": "element-1"}
    assert asserted["success"] is True
    assert screenshot == "c2NyZWVu"
    assert fake.requests[0][2]["capabilities"]["alwaysMatch"]["appium:automationName"] == "XCUITest"
    assert any(item[0] == "DELETE" and item[1].endswith("/session/ios-session") for item in fake.requests)


def test_ios_helpers_render_nested_variables_and_build_touch_actions():
    rendered = _render_params({"text": "{{USER}}", "nested": ["{{TOKEN}}"]}, {"USER": "parado", "TOKEN": "t-1"})
    assert rendered == {"text": "parado", "nested": ["t-1"]}

    action = _touch_actions({"x": 10, "y": 20, "to_x": 110, "to_y": 220, "duration_ms": 400}, "swipe")
    assert action["parameters"]["pointerType"] == "touch"
    assert action["actions"][-2]["type"] == "pointerMove"
    assert action["actions"][-2]["x"] == 110


def test_appium_client_rejects_protocol_error():
    class ErrorHttp(_FakeHttp):
        async def request(self, method, url, json=None):
            return _Response(500, {"value": {"error": "session not created"}})

    client = IosAppiumClient("http://mac-worker:4723", http_client=ErrorHttp())

    async def run():
        try:
            await client.start_session(
                udid="device-1", device_name=None, platform_version=None, bundle_id=None, app=None
            )
        except RuntimeError as exc:
            return str(exc)
        raise AssertionError("expected Appium protocol failure")

    assert "session not created" in asyncio.run(run())


def test_appium_client_dispatches_remaining_actions_and_lifecycle_calls():
    fake = _FakeHttp()
    client = IosAppiumClient("http://mac-worker:4723", http_client=fake)

    async def run():
        await client.start_session(udid="device-1", device_name=None, platform_version=None, bundle_id=None, app=None)
        failed_assert = await client.execute_step("assert_text", {"text": "不存在"})
        waited = await client.execute_step("wait", {"seconds": 0})
        screenshot = await client.execute_step("screenshot", {})
        await client.execute_step("input", {"strategy": "id", "value": "email", "text": "x", "clear": False})
        await client.execute_step("back", {})
        await client.execute_step("start_app", {"bundle_id": "com.example.app"})
        await client.execute_step("stop_app", {"bundle_id": "com.example.app"})
        source = await client.execute_step("get_source", {})
        await client.execute_step("tap", {"x": 10, "y": 20})
        await client.execute_step("swipe", {"x": 10, "y": 20, "to_x": 50, "to_y": 60})
        await client.start_recording()
        recording = await client.stop_recording()
        logs = await client.syslog()
        with pytest.raises(RuntimeError, match="未知 iOS 操作类型"):
            await client.execute_step("unsupported", {})
        await client.quit()
        return failed_assert, waited, screenshot, source, recording, logs

    failed_assert, waited, screenshot, source, recording, logs = asyncio.run(run())

    assert failed_assert["success"] is False
    assert waited == {"success": True, "wait_seconds": 0.0}
    assert screenshot["screenshot_base64"] == "c2NyZWVu"
    assert source["source"].startswith("<XCUIElementTypeStaticText")
    assert recording is None
    assert logs == "{}"
    assert any(item[1].endswith("/back") for item in fake.requests)
    assert any(item[1].endswith("/appium/device/activate_app") for item in fake.requests)
    assert any(item[1].endswith("/actions") for item in fake.requests)


def test_appium_client_rejects_invalid_payloads_and_missing_session():
    client = IosAppiumClient("http://mac-worker:4723", http_client=_FakeHttp())

    async def run():
        errors = []
        for action, params in (("click", {}), ("screenshot", {})):
            try:
                await client.execute_step(action, params)
            except RuntimeError as exc:
                errors.append(str(exc))
        return errors

    errors = asyncio.run(run())
    assert any("会话尚未建立" in item for item in errors)
