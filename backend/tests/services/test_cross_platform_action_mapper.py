"""跨端统一语义动作模型与映射器单测 (T1.1)"""

from __future__ import annotations

from app.services.cross_platform_action_mapper import (
    ActionMappingResult,
    PlatformType,
    SemanticActionType,
    SemanticLocator,
    convert_locator_for_platform,
    map_action_step,
    map_cross_platform_actions,
)


def test_convert_locator_same_platform():
    loc = SemanticLocator("id", "btn_submit", element_text="提交")
    target_loc, conf = convert_locator_for_platform(loc, PlatformType.WEB, PlatformType.WEB)
    assert target_loc == loc
    assert conf == 1.0


def test_convert_locator_web_to_android_and_ios():
    # 1. 纯文本对齐
    loc_text = SemanticLocator("text", "立即购买", element_text="立即购买")
    android_loc, conf = convert_locator_for_platform(loc_text, PlatformType.WEB, PlatformType.ANDROID)
    assert android_loc.locator_type == "text"
    assert android_loc.locator_value == "立即购买"
    assert conf >= 0.9

    ios_loc, conf_ios = convert_locator_for_platform(loc_text, PlatformType.WEB, PlatformType.IOS)
    assert ios_loc.locator_type == "accessibility_id"
    assert ios_loc.locator_value == "立即购买"
    assert conf_ios >= 0.9

    # 2. CSS ID 对齐
    loc_id = SemanticLocator("css", "#checkout-btn")
    android_id_loc, _ = convert_locator_for_platform(loc_id, PlatformType.WEB, PlatformType.ANDROID)
    assert android_id_loc.locator_type == "resource_id"
    assert android_id_loc.locator_value == "checkout-btn"


def test_convert_locator_ios_to_android():
    loc = SemanticLocator("accessibility_id", "pay_button", semantic_role="button")
    android_loc, conf = convert_locator_for_platform(loc, PlatformType.IOS, PlatformType.ANDROID)
    assert android_loc.locator_type == "resource_id"
    assert android_loc.locator_value == "pay_button"
    assert conf >= 0.9


def test_convert_locator_android_to_ios():
    loc = SemanticLocator("resource_id", "com.shop.app:id/submit_order")
    ios_loc, conf = convert_locator_for_platform(loc, PlatformType.ANDROID, PlatformType.IOS)
    assert ios_loc.locator_type == "accessibility_id"
    assert ios_loc.locator_value == "submit_order"
    assert conf >= 0.9


def test_map_single_action_step():
    raw_step = {
        "step_id": "s1",
        "action_type": "FILL_TEXT",
        "locator": {"type": "id", "value": "username_field", "text": "账号输入框"},
        "input_text": "admin_user",
    }
    step = map_action_step(raw_step, PlatformType.WEB, PlatformType.IOS)
    assert step.step_id == "s1"
    assert step.action_type == SemanticActionType.FILL_TEXT
    assert step.source_platform == PlatformType.WEB
    assert step.target_platform == PlatformType.IOS
    assert step.parameters.get("text") == "admin_user"
    assert step.target_locator is not None
    assert step.confidence >= 0.8


def test_map_cross_platform_actions_batch():
    raw_steps = [
        {
            "step_id": "step_01",
            "action_type": "TAP",
            "locator": {"type": "accessibility_id", "value": "login_btn", "text": "登录"},
        },
        {
            "step_id": "step_02",
            "action_type": "FILL_TEXT",
            "locator": {"type": "id", "value": "pwd_input"},
            "input_text": "secret123",
        },
        {
            "step_id": "step_03",
            "action_type": "ASSERT_TEXT",
            "locator": {"type": "id", "value": "welcome_banner"},
            "expected_text": "欢迎回来",
        },
    ]

    res = map_cross_platform_actions(raw_steps, PlatformType.IOS, PlatformType.ANDROID)
    assert isinstance(res, ActionMappingResult)
    assert res.mapping_id.startswith("map_")
    assert res.total_steps == 3
    assert res.mapped_steps_count == 3
    assert res.average_confidence >= 0.8

    # 验证序列化字典
    d = res.to_dict()
    assert d["source_platform"] == "ios"
    assert d["target_platform"] == "android"
    assert len(d["mapped_steps"]) == 3
