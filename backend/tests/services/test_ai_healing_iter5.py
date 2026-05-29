import pytest
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from app.services.ai_healing_iter5 import (
    StructuredHealingPatch,
    build_structured_healing_prompt,
    parse_structured_healing_suggestion,
    validate_lowcode_patch,
)


def test_build_structured_prompt_demands_json_contract():
    prompt = build_structured_healing_prompt(
        case_type="web",
        case_name="login",
        step_index=1,
        step_name="click login",
        current_step={"action": "click", "params": {"selector": "#login"}},
        error_message="Timeout waiting for selector",
        screenshot_available=True,
    )

    assert "只输出一个 JSON 对象" in prompt
    assert '"root_cause"' in prompt
    assert '"patch"' in prompt
    assert "failed_step_index: 1" in prompt


def test_parse_structured_suggestion_accepts_fenced_json():
    suggestion = parse_structured_healing_suggestion(
        """```json
        {
          "root_cause": "selector changed",
          "confidence": 1.5,
          "patch": {
            "case_type": "web",
            "step_index": 0,
            "action": "click",
            "params": {"selector": "button[type=submit]"}
          },
          "regression_scope": "suite",
          "notes": ["review selector"]
        }
        ```"""
    )

    assert suggestion.root_cause == "selector changed"
    assert suggestion.confidence == 1.0
    assert suggestion.patch is not None
    assert suggestion.patch.params["selector"] == "button[type=submit]"
    assert suggestion.regression_scope == "suite"


def test_parse_structured_suggestion_rejects_invalid_json():
    with pytest.raises(ValueError, match="invalid_structured_healing_json"):
        parse_structured_healing_suggestion('{"root_cause": "x",}')


def test_validate_web_patch_previews_allowed_param_update_without_mutating_input():
    config = {"steps": [{"action": "click", "params": {"selector": "#old"}}]}
    result = validate_lowcode_patch(
        case_type="web",
        case_config=config,
        patch=StructuredHealingPatch(
            case_type="web",
            step_index=0,
            action="click",
            params={"selector": "#new", "timeout_ms": 999999},
        ),
    )

    assert result.accepted is True
    assert result.preview_config["steps"][0]["params"]["selector"] == "#new"
    assert result.preview_config["steps"][0]["params"]["timeout_ms"] == 30000
    assert config["steps"][0]["params"] == {"selector": "#old"}


def test_validate_android_patch_accepts_resource_id_alias():
    config = {"steps": [{"action": "assert_element", "params": {"resourceId": "old"}}]}
    result = validate_lowcode_patch(
        case_type="android",
        case_config=config,
        patch=StructuredHealingPatch(
            case_type="android",
            step_index=0,
            action="assert_element",
            params={"resource_id": "com.app:id/title"},
        ),
    )

    assert result.accepted is True
    assert result.preview_config["steps"][0]["params"]["resource_id"] == "com.app:id/title"


def test_validate_patch_rejects_secret_like_params():
    config = {"steps": [{"action": "fill", "params": {"selector": "#password"}}]}
    result = validate_lowcode_patch(
        case_type="web",
        case_config=config,
        patch=StructuredHealingPatch(
            case_type="web",
            step_index=0,
            action="fill",
            params={"selector": "#password", "token": "abc"},
        ),
    )

    assert result.accepted is False
    assert "denied_param:token" in result.reasons


def test_validate_patch_rejects_action_replacement_for_now():
    config = {"steps": [{"action": "click", "params": {"selector": "#old"}}]}
    result = validate_lowcode_patch(
        case_type="web",
        case_config=config,
        patch=StructuredHealingPatch(
            case_type="web",
            step_index=0,
            action="fill",
            params={"selector": "#old", "value": "x"},
        ),
    )

    assert result.accepted is False
    assert result.reasons == ["action_replacement_requires_manual_design"]
