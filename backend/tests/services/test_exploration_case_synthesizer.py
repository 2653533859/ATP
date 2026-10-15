"""Unit tests for Q2.2 Exploration Event Sequence to TestCase Synthesizer.

Tests:
1. clean_and_compress_events collapses duplicate clicks and merges consecutive text inputs
2. synthesize_case_steps transforms raw events into CaseStepCreate items and low-code configs
3. Automatic terminal state assertion synthesis
4. synthesize_test_case_payload produces valid TestCaseCreate schema instances
"""

from app.models.bootstrap import load_all_models
from app.schemas.case import TestCaseCreate
from app.services.exploration_case_synthesizer import (
    clean_and_compress_events,
    synthesize_case_steps,
    synthesize_test_case_payload,
)

load_all_models()


def test_clean_and_compress_events():
    raw_events = [
        # Double click on same button
        {
            "action_type": "click",
            "element": {"id": "btn_submit", "text": "提交"},
            "action_signature": "click_btn_submit",
        },
        {
            "action_type": "click",
            "element": {"id": "btn_submit", "text": "提交"},
            "action_signature": "click_btn_submit",
        },
        # Partial typing into username field
        {"action_type": "input", "element": {"id": "edt_username"}, "input_text": "use"},
        {"action_type": "input", "element": {"id": "edt_username"}, "input_text": "user_admin"},
        # Distinct click
        {"action_type": "click", "element": {"id": "btn_next", "text": "下一步"}, "action_signature": "click_btn_next"},
    ]

    compressed = clean_and_compress_events(raw_events)

    # 1. Double click collapsed to 1
    # 2. Input collapsed to the final 'user_admin'
    # 3. Final click preserved
    assert len(compressed) == 3
    assert compressed[0]["element"]["id"] == "btn_submit"
    assert compressed[1]["action_type"] == "input"
    assert compressed[1]["input_text"] == "user_admin"
    assert compressed[2]["element"]["id"] == "btn_next"


def test_synthesize_case_steps_generation():
    events = [
        {
            "action_type": "click",
            "screen_name": "LoginActivity",
            "element": {"id": "btn_login", "text": "登录"},
            "next_screen": "PasswordActivity",
        },
        {
            "action_type": "input",
            "screen_name": "PasswordActivity",
            "element": {"id": "edt_pwd"},
            "input_text": "Pass@123",
        },
        {
            "action_type": "click",
            "screen_name": "PasswordActivity",
            "element": {"id": "btn_confirm", "text": "确认"},
            "next_screen": "DashboardScreen",
        },
    ]

    case_steps, config_steps = synthesize_case_steps(events, platform="android")

    # 3 event steps + 1 auto-synthesized terminal verification step = 4 steps
    assert len(case_steps) == 4
    assert len(config_steps) == 4

    # Step 1: Click login
    assert case_steps[0].step_no == 1
    assert case_steps[0].action == "click"
    assert "PasswordActivity" in str(case_steps[0].expected_result)
    assert config_steps[0]["action"] == "click"
    assert config_steps[0]["params"]["value"] == "btn_login"

    # Step 2: Input password
    assert case_steps[1].step_no == 2
    assert case_steps[1].action == "input"
    assert case_steps[1].test_data == "Pass@123"

    # Step 4: Terminal assert_text verification step
    assert case_steps[3].step_no == 4
    assert case_steps[3].action == "assert_text"
    assert case_steps[3].test_data == "DashboardScreen"
    assert case_steps[3].is_key_step is True


def test_synthesize_test_case_payload():
    events = [
        {"action_type": "click", "element": {"id": "tab_orders", "text": "订单"}},
        {"action_type": "swipe", "params": {"x": 100, "y": 800, "to_x": 100, "to_y": 200}},
    ]

    payload = synthesize_test_case_payload(
        name="智能订单列表探索用例",
        module_id=42,
        events=events,
        case_type="android",
    )

    assert isinstance(payload, TestCaseCreate)
    assert payload.name == "智能订单列表探索用例"
    assert payload.module_id == 42
    assert payload.case_type == "android"
    assert "ai_synthesized" in payload.tags
    assert len(payload.steps) == 2
    assert len(payload.config["steps"]) == 2
    assert payload.config["platform"] == "android"
