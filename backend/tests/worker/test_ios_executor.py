"""Behavior tests for the Appium protocol boundary."""

import asyncio

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
