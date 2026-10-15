"""Unit tests for T2.1 Android and iOS Unified Device Playback Driver and Execution Lifecycle.

Tests:
1. initialize_playback_session validates platforms and creates active sessions
2. AndroidPlaybackAdapter dispatches click, input, swipe, press_key, assert_text
3. IosPlaybackAdapter dispatches click, input, swipe, press_key, assert_text
4. DevicePlaybackSession replaces context variables and records step diagnostics
5. DevicePlaybackSession handles assertion failure and error states
6. teardown_playback_session cleans up adapter and compiles final summary
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock
import pytest

from app.services.device_playback_driver import (
    AndroidPlaybackAdapter,
    IosPlaybackAdapter,
    get_playback_session,
    initialize_playback_session,
    teardown_playback_session,
)


@pytest.mark.asyncio
async def test_initialize_playback_session():
    # Unsupported platform
    with pytest.raises(ValueError, match="不支持的设备平台"):
        await initialize_playback_session("windows_desktop", 1, "serial_1", "com.app")

    # Android session with mock adapter
    mock_u2 = MagicMock()
    mock_adapter = AndroidPlaybackAdapter("serial_123", "com.example.app", mock_driver=mock_u2)
    session = await initialize_playback_session(
        "android",
        device_id=1,
        serial_or_udid="serial_123",
        target_app="com.example.app",
        custom_adapter=mock_adapter,
        session_id="play_test_01",
    )

    assert session.session_id == "play_test_01"
    assert session.platform == "android"
    assert session.status == "running"
    assert session.adapter.is_connected is True
    assert get_playback_session("play_test_01") is session


@pytest.mark.asyncio
async def test_android_playback_adapter_actions():
    mock_u2 = MagicMock()
    adapter = AndroidPlaybackAdapter("emulator-5554", "com.shop.app", mock_driver=mock_u2)
    await adapter.connect()

    # 1. Click
    await adapter.click({"text": "登录"})
    mock_u2.assert_called_with(text="登录")

    # 2. Input
    await adapter.input_text({"resource_id": "txt_user", "text": "test_user"})
    mock_u2.assert_called_with(resourceId="txt_user")

    # 3. Swipe
    await adapter.swipe({"direction": "down"})
    mock_u2.swipe_ext.assert_called_with("down")

    # 4. Press key
    await adapter.press_key({"key": "home"})
    mock_u2.press.assert_called_with("home")


@pytest.mark.asyncio
async def test_ios_playback_adapter_actions():
    mock_client = AsyncMock()
    mock_client.find_element.return_value = {"ELEMENT": "elem_id_101"}
    adapter = IosPlaybackAdapter("00008101-001A", "com.apple.Preferences", mock_client=mock_client)
    await adapter.connect()

    # 1. Click
    await adapter.click({"accessibility_id": "General"})
    mock_client.find_element.assert_called_with("accessibility id", "General")
    mock_client.click_element.assert_called_with("elem_id_101")

    # 2. Input
    await adapter.input_text({"accessibility_id": "SearchField", "text": "Wi-Fi"})
    mock_client.send_keys.assert_called_with("elem_id_101", "Wi-Fi")

    # 3. Swipe
    await adapter.swipe({"direction": "up"})
    mock_client.execute_script.assert_called_with("mobile: swipe", {"direction": "up"})


@pytest.mark.asyncio
async def test_session_execution_lifecycle_and_context_vars():
    mock_u2 = MagicMock()
    mock_element = MagicMock()
    mock_element.exists.return_value = True
    mock_u2.return_value = mock_element

    adapter = AndroidPlaybackAdapter("emulator-5554", "com.demo.app", mock_driver=mock_u2)
    session = await initialize_playback_session(
        "android",
        device_id=1,
        serial_or_udid="emulator-5554",
        target_app="com.demo.app",
        custom_adapter=adapter,
        session_id="play_test_lifecycle",
    )

    # Set context variables from previous steps (e.g. from T1.2 extractors)
    session.context["username"] = "alice_vip"
    session.context["order_id"] = "ORD-9988"

    # Step 1: Input text with {{username}} variable
    rec1 = await session.execute_step(
        {"action": "input", "params": {"resource_id": "user_input", "text": "user_{{username}}"}},
        step_no=1,
    )
    assert rec1.status == "passed"
    assert rec1.params["text"] == "user_alice_vip"

    # Step 2: Assert text with {{order_id}} variable
    rec2 = await session.execute_step(
        {"action": "assert_text", "params": {"expected_text": "订单 {{order_id}} 支付成功", "timeout": 2.0}},
        step_no=2,
    )
    assert rec2.status == "passed"
    assert rec2.params["expected_text"] == "订单 ORD-9988 支付成功"

    # Step 3: Wait step
    rec3 = await session.execute_step({"action": "wait", "params": {"seconds": 0.1}}, step_no=3)
    assert rec3.status == "passed"

    # Step 4: Teardown
    summary = await teardown_playback_session("play_test_lifecycle")
    assert summary is not None
    assert summary["status"] == "completed"
    assert summary["total_steps"] == 3
    assert summary["passed_steps"] == 3
    assert summary["failed_steps"] == 0


@pytest.mark.asyncio
async def test_session_assertion_failure_and_error_handling():
    mock_u2 = MagicMock()
    mock_element = MagicMock()
    # Simulate element NOT found on screen
    mock_element.exists.return_value = False
    mock_u2.return_value = mock_element

    adapter = AndroidPlaybackAdapter("emulator-5554", "com.demo.app", mock_driver=mock_u2)
    session = await initialize_playback_session(
        "android",
        device_id=1,
        serial_or_udid="emulator-5554",
        target_app="com.demo.app",
        custom_adapter=adapter,
        session_id="play_test_fail",
    )

    # 1. Assert text failure
    rec_fail = await session.execute_step(
        {"action": "assert_text", "params": {"expected_text": "不存在的成功提示"}},
        step_no=1,
    )
    assert rec_fail.status == "failed"
    assert "未在页面找到期望文本" in str(rec_fail.error_message)

    # 2. Unsupported action error
    rec_err = await session.execute_step(
        {"action": "unknown_action_xyz", "params": {}},
        step_no=2,
    )
    assert rec_err.status == "error"
    assert "不支持的真机回放动作" in str(rec_err.error_message)

    # 3. Teardown should reflect failed status
    summary = await teardown_playback_session("play_test_fail")
    assert summary is not None
    assert summary["status"] == "failed"
    assert summary["failed_steps"] == 1
    assert summary["error_steps"] == 1
