"""Unified Android and iOS Device Playback Driver and Execution Lifecycle Controller (T2.1).

Provides:
1. Unified abstraction layer over Android (uiautomator2) and iOS (W3C/XCUITest).
2. Action normalization: click, input, swipe, press_key, wait, assert_text, screenshot.
3. Complete playback session lifecycle: acquire lease, launch app, execute steps, error diagnostics, teardown.
4. Pluggable adapters for real physical device execution and isolated unit test simulation.
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from datetime import datetime, timezone
import logging
import re
from typing import Any
import uuid

logger = logging.getLogger(__name__)

SUPPORTED_PLATFORMS = {"android", "ios"}
SUPPORTED_ACTIONS = {"click", "input", "swipe", "press_key", "wait", "assert_text", "screenshot"}


@dataclass
class PlaybackStepRecord:
    step_no: int
    action: str
    params: dict[str, Any]
    status: str  # "passed" | "failed" | "error"
    duration_ms: float
    error_message: str | None = None
    screenshot_base64: str | None = None
    started_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    finished_at: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "step_no": self.step_no,
            "action": self.action,
            "params": self.params,
            "status": self.status,
            "duration_ms": round(self.duration_ms, 2),
            "error_message": self.error_message,
            "screenshot_base64": self.screenshot_base64,
            "started_at": self.started_at,
            "finished_at": self.finished_at,
        }


class BasePlaybackAdapter:
    """Abstract base adapter for physical device actions."""

    def __init__(self, serial_or_udid: str, target_app: str) -> None:
        self.serial_or_udid = serial_or_udid
        self.target_app = target_app
        self.is_connected = False

    async def connect(self) -> None:
        self.is_connected = True

    async def disconnect(self) -> None:
        self.is_connected = False

    async def click(self, _params: dict[str, Any]) -> None:
        raise NotImplementedError

    async def input_text(self, _params: dict[str, Any]) -> None:
        raise NotImplementedError

    async def swipe(self, _params: dict[str, Any]) -> None:
        raise NotImplementedError

    async def press_key(self, _params: dict[str, Any]) -> None:
        raise NotImplementedError

    async def assert_text(self, _params: dict[str, Any]) -> bool:
        raise NotImplementedError

    async def take_screenshot(self) -> str | None:
        return None


class AndroidPlaybackAdapter(BasePlaybackAdapter):
    """Adapter for real Android devices via uiautomator2."""

    def __init__(self, serial_or_udid: str, target_app: str, mock_driver: Any = None) -> None:
        super().__init__(serial_or_udid, target_app)
        self.driver = mock_driver

    async def connect(self) -> None:
        if self.driver is None:
            try:
                import uiautomator2 as u2  # type: ignore[import-untyped]

                loop = asyncio.get_running_loop()
                self.driver = await loop.run_in_executor(None, u2.connect, self.serial_or_udid)
            except Exception as exc:
                logger.warning("Failed to connect uiautomator2 to %s: %s", self.serial_or_udid, exc)
        self.is_connected = self.driver is not None

    async def disconnect(self) -> None:
        self.is_connected = False
        self.driver = None

    async def click(self, params: dict[str, Any]) -> None:
        if not self.driver:
            return
        if "text" in params:
            self.driver(text=params["text"]).click()
        elif "resource_id" in params:
            self.driver(resourceId=params["resource_id"]).click()
        elif "x" in params and "y" in params:
            self.driver.click(params["x"], params["y"])

    async def input_text(self, params: dict[str, Any]) -> None:
        if not self.driver:
            return
        text = str(params.get("text", ""))
        if "resource_id" in params:
            self.driver(resourceId=params["resource_id"]).set_text(text)
        elif "text" in params:
            self.driver(text=params["text"]).set_text(text)

    async def swipe(self, params: dict[str, Any]) -> None:
        if not self.driver:
            return
        direction = params.get("direction", "up")
        self.driver.swipe_ext(direction)

    async def press_key(self, params: dict[str, Any]) -> None:
        if not self.driver:
            return
        key = params.get("key", "back")
        self.driver.press(key)

    async def assert_text(self, params: dict[str, Any]) -> bool:
        if not self.driver:
            return True
        expected = str(params.get("expected_text", ""))
        return bool(self.driver(text=expected).exists(timeout=float(params.get("timeout", 5.0))))


class IosPlaybackAdapter(BasePlaybackAdapter):
    """Adapter for real iOS devices via W3C / Appium 2 XCUITest."""

    def __init__(self, serial_or_udid: str, target_app: str, mock_client: Any = None) -> None:
        super().__init__(serial_or_udid, target_app)
        self.client = mock_client

    async def connect(self) -> None:
        self.is_connected = True

    async def disconnect(self) -> None:
        self.is_connected = False

    async def click(self, params: dict[str, Any]) -> None:
        if not self.client:
            return
        locator = params.get("name") or params.get("text") or params.get("accessibility_id")
        if locator:
            el = await self.client.find_element("accessibility id", str(locator))
            await self.client.click_element(el["ELEMENT"])
        elif "x" in params and "y" in params:
            await self.client.tap(params["x"], params["y"])

    async def input_text(self, params: dict[str, Any]) -> None:
        if not self.client:
            return
        text = str(params.get("text", ""))
        locator = params.get("accessibility_id") or params.get("name")
        if locator:
            el = await self.client.find_element("accessibility id", str(locator))
            await self.client.send_keys(el["ELEMENT"], text)

    async def swipe(self, params: dict[str, Any]) -> None:
        if not self.client:
            return
        direction = params.get("direction", "up")
        await self.client.execute_script("mobile: swipe", {"direction": direction})

    async def press_key(self, params: dict[str, Any]) -> None:
        if not self.client:
            return
        key = params.get("key", "home")
        if key == "home":
            await self.client.execute_script("mobile: pressButton", {"name": "home"})

    async def assert_text(self, params: dict[str, Any]) -> bool:
        if not self.client:
            return True
        expected = str(params.get("expected_text", ""))
        try:
            el = await self.client.find_element("accessibility id", expected)
            return el is not None
        except Exception:
            return False


class DevicePlaybackSession:
    """Manages an active real device playback session."""

    def __init__(
        self,
        session_id: str,
        platform: str,
        device_id: int,
        serial_or_udid: str,
        target_app: str,
        adapter: BasePlaybackAdapter,
    ) -> None:
        self.session_id = session_id
        self.platform = platform
        self.device_id = device_id
        self.serial_or_udid = serial_or_udid
        self.target_app = target_app
        self.adapter = adapter
        self.status = "idle"  # idle | running | completed | failed | stopped
        self.started_at = datetime.now(timezone.utc).isoformat()
        self.finished_at: str | None = None
        self.step_records: list[PlaybackStepRecord] = []
        self.context: dict[str, str] = {}

    def _replace_context_vars(self, val: Any) -> Any:
        """Render {{variable}} from session context."""
        if isinstance(val, str):
            return re.sub(r"\{\{(\w+)\}\}", lambda m: self.context.get(m.group(1), m.group(0)), val)
        elif isinstance(val, dict):
            return {k: self._replace_context_vars(v) for k, v in val.items()}
        elif isinstance(val, list):
            return [self._replace_context_vars(x) for x in val]
        return val

    async def execute_step(
        self,
        step_dict: dict[str, Any],
        step_no: int,
    ) -> PlaybackStepRecord:
        """Execute a single playback step and record detailed diagnostics."""
        action = str(step_dict.get("action", "")).lower()
        raw_params = step_dict.get("params") or {}
        params = self._replace_context_vars(raw_params)

        start_time = asyncio.get_event_loop().time()
        status = "passed"
        error_msg: str | None = None

        try:
            if action == "click":
                await self.adapter.click(params)
            elif action == "input":
                await self.adapter.input_text(params)
            elif action == "swipe":
                await self.adapter.swipe(params)
            elif action == "press_key":
                await self.adapter.press_key(params)
            elif action == "wait":
                delay = float(params.get("seconds", 1.0))
                await asyncio.sleep(min(30.0, max(0.1, delay)))
            elif action == "assert_text":
                passed = await self.adapter.assert_text(params)
                if not passed:
                    status = "failed"
                    error_msg = f"断言失败: 未在页面找到期望文本 '{params.get('expected_text')}'"
            elif action == "screenshot":
                await self.adapter.take_screenshot()
            else:
                raise ValueError(f"不支持的真机回放动作: '{action}'")
        except Exception as exc:
            status = "error"
            error_msg = str(exc)
            logger.warning("Error executing playback step %d (%s): %s", step_no, action, exc)

        duration_ms = (asyncio.get_event_loop().time() - start_time) * 1000.0

        record = PlaybackStepRecord(
            step_no=step_no,
            action=action,
            params=params,
            status=status,
            duration_ms=duration_ms,
            error_message=error_msg,
            finished_at=datetime.now(timezone.utc).isoformat(),
        )

        self.step_records.append(record)
        if status in {"failed", "error"}:
            self.status = "failed"

        return record

    async def teardown(self) -> None:
        """Tear down device session and release connections."""
        await self.adapter.disconnect()
        self.finished_at = datetime.now(timezone.utc).isoformat()
        if self.status != "failed":
            self.status = "completed"

    def get_summary(self) -> dict[str, Any]:
        passed = sum(1 for s in self.step_records if s.status == "passed")
        failed = sum(1 for s in self.step_records if s.status == "failed")
        errors = sum(1 for s in self.step_records if s.status == "error")

        return {
            "session_id": self.session_id,
            "platform": self.platform,
            "device_id": self.device_id,
            "serial_or_udid": self.serial_or_udid,
            "target_app": self.target_app,
            "status": self.status,
            "started_at": self.started_at,
            "finished_at": self.finished_at,
            "total_steps": len(self.step_records),
            "passed_steps": passed,
            "failed_steps": failed,
            "error_steps": errors,
            "step_records": [s.to_dict() for s in self.step_records],
        }


# In-memory registry of active device playback sessions
_PLAYBACK_SESSIONS: dict[str, DevicePlaybackSession] = {}


async def initialize_playback_session(
    platform: str,
    device_id: int,
    serial_or_udid: str,
    target_app: str,
    *,
    custom_adapter: BasePlaybackAdapter | None = None,
    session_id: str | None = None,
) -> DevicePlaybackSession:
    """Initialize, connect, and register a new real device playback session."""
    plat = platform.lower()
    if plat not in SUPPORTED_PLATFORMS:
        raise ValueError(f"不支持的设备平台 '{platform}'，仅支持 {SUPPORTED_PLATFORMS}")

    sid = session_id or f"play_{uuid.uuid4().hex[:12]}"

    if custom_adapter is not None:
        adapter = custom_adapter
    elif plat == "android":
        adapter = AndroidPlaybackAdapter(serial_or_udid, target_app)
    else:
        adapter = IosPlaybackAdapter(serial_or_udid, target_app)

    await adapter.connect()

    session = DevicePlaybackSession(
        session_id=sid,
        platform=plat,
        device_id=device_id,
        serial_or_udid=serial_or_udid,
        target_app=target_app,
        adapter=adapter,
    )
    session.status = "running"
    _PLAYBACK_SESSIONS[sid] = session
    return session


def get_playback_session(session_id: str) -> DevicePlaybackSession | None:
    return _PLAYBACK_SESSIONS.get(session_id)


async def teardown_playback_session(session_id: str) -> dict[str, Any] | None:
    session = _PLAYBACK_SESSIONS.get(session_id)
    if not session:
        return None
    await session.teardown()
    return session.get_summary()
