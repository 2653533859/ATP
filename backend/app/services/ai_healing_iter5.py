"""Q8 AI healing iter5 helpers.

This module is intentionally side-effect free: it defines the structured LLM
contract and validates low-code patches before any future API writes them back.
"""

from __future__ import annotations

import copy
import json
import re
from dataclasses import dataclass, field
from typing import Any


WEB_ACTION_PARAM_ALLOWLIST: dict[str, set[str]] = {
    "click": {"selector", "timeout_ms"},
    "fill": {"selector", "value", "timeout_ms"},
    "assert_text": {"text", "timeout_ms"},
    "assert_visible": {"selector", "timeout_ms"},
    "wait": {"ms"},
    "select": {"selector", "value", "timeout_ms"},
    "press": {"selector", "key", "timeout_ms"},
    "hover": {"selector", "timeout_ms"},
}

ANDROID_ACTION_PARAM_ALLOWLIST: dict[str, set[str]] = {
    "click": {"text", "resourceId", "resource_id", "x", "y"},
    "long_click": {"x", "y", "duration"},
    "swipe": {"direction", "x1", "y1", "x2", "y2", "duration"},
    "input": {"text", "value", "resourceId", "resource_id", "clear"},
    "press_key": {"key"},
    "assert_text": {"text"},
    "assert_element": {"resourceId", "resource_id"},
    "wait": {"ms"},
}

_DENIED_PARAM_KEYS = {
    "api_key",
    "authorization",
    "cookie",
    "headers",
    "password",
    "secret",
    "token",
}
_MAX_TEXT_PARAM_LENGTH = 500
_MAX_WAIT_MS = 30_000


@dataclass(frozen=True)
class StructuredHealingPatch:
    case_type: str
    step_index: int
    action: str
    params: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class StructuredHealingSuggestion:
    root_cause: str
    confidence: float
    patch: StructuredHealingPatch | None = None
    regression_scope: str = "single_case"
    notes: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class PatchValidationResult:
    accepted: bool
    reasons: list[str] = field(default_factory=list)
    normalized_patch: StructuredHealingPatch | None = None
    preview_config: dict[str, Any] | None = None


def build_structured_healing_prompt(
    *,
    case_type: str,
    case_name: str,
    step_index: int,
    step_name: str,
    current_step: dict[str, Any] | None,
    error_message: str | None,
    screenshot_available: bool = False,
) -> str:
    """Build a prompt that asks the LLM for the iter5 JSON contract only."""
    current_step_json = json.dumps(current_step or {}, ensure_ascii=False, indent=2)
    return "\n".join(
        [
            "你是 ATP 自动化测试平台的用例自愈助手。",
            "只输出一个 JSON 对象，不要输出 Markdown、解释文本或代码块。",
            "允许建议的 patch 仅用于低代码 Web/Android 步骤，并且必须经过人工确认后才能应用。",
            "",
            f"case_type: {case_type}",
            f"case_name: {case_name}",
            f"failed_step_index: {step_index}",
            f"failed_step_name: {step_name}",
            f"screenshot_available: {str(screenshot_available).lower()}",
            "current_step:",
            current_step_json,
            "error_message:",
            error_message or "",
            "",
            "JSON schema:",
            json.dumps(
                {
                    "root_cause": "one sentence",
                    "confidence": 0.0,
                    "patch": {
                        "case_type": case_type,
                        "step_index": step_index,
                        "action": "same low-code action unless a replacement is necessary",
                        "params": {"selector": "safe replacement fields only"},
                    },
                    "regression_scope": "single_case",
                    "notes": ["short reviewer-facing note"],
                },
                ensure_ascii=False,
                indent=2,
            ),
        ]
    )


def parse_structured_healing_suggestion(text: str) -> StructuredHealingSuggestion:
    """Parse a structured suggestion from raw LLM text.

    Accepts plain JSON or a fenced JSON block. Raises ValueError with a stable
    message when the payload is invalid.
    """
    payload = _extract_json_payload(text)
    try:
        raw = json.loads(payload)
    except json.JSONDecodeError as exc:
        raise ValueError("invalid_structured_healing_json") from exc
    if not isinstance(raw, dict):
        raise ValueError("structured_healing_payload_must_be_object")

    root_cause = _require_str(raw, "root_cause")
    confidence = _normalize_confidence(raw.get("confidence", 0.0))
    patch = _parse_patch(raw.get("patch"))
    regression_scope = raw.get("regression_scope") or "single_case"
    if regression_scope not in {"single_case", "suite", "manual"}:
        regression_scope = "single_case"
    notes_raw = raw.get("notes") or []
    notes = [str(item)[:200] for item in notes_raw if isinstance(item, (str, int, float))]

    return StructuredHealingSuggestion(
        root_cause=root_cause,
        confidence=confidence,
        patch=patch,
        regression_scope=regression_scope,
        notes=notes,
    )


def validate_lowcode_patch(
    *,
    case_type: str,
    case_config: dict[str, Any],
    patch: StructuredHealingPatch | None,
) -> PatchValidationResult:
    """Validate and preview a low-code patch without mutating input config."""
    if patch is None:
        return PatchValidationResult(False, ["missing_patch"])
    normalized_type = _normalize_case_type(case_type)
    if normalized_type not in {"web", "android"}:
        return PatchValidationResult(False, ["unsupported_case_type"])
    if _normalize_case_type(patch.case_type) != normalized_type:
        return PatchValidationResult(False, ["patch_case_type_mismatch"])

    steps = case_config.get("steps")
    if not isinstance(steps, list):
        return PatchValidationResult(False, ["case_config_steps_missing"])
    if patch.step_index < 0 or patch.step_index >= len(steps):
        return PatchValidationResult(False, ["step_index_out_of_range"])
    current_step = steps[patch.step_index]
    if not isinstance(current_step, dict):
        return PatchValidationResult(False, ["target_step_invalid"])

    action = str(patch.action or current_step.get("action") or "")
    allowlist = _allowlist_for(normalized_type)
    if action not in allowlist:
        return PatchValidationResult(False, ["unsupported_action"])

    current_action = str(current_step.get("action") or "")
    if current_action and action != current_action:
        return PatchValidationResult(False, ["action_replacement_requires_manual_design"])

    normalized_params, reasons = _normalize_params(action, patch.params, allowlist[action])
    if reasons:
        return PatchValidationResult(False, reasons)

    preview = copy.deepcopy(case_config)
    preview_steps = preview["steps"]
    preview_step = preview_steps[patch.step_index]
    preview_step["action"] = action
    preview_step["params"] = {**(preview_step.get("params") or {}), **normalized_params}

    normalized_patch = StructuredHealingPatch(
        case_type=normalized_type,
        step_index=patch.step_index,
        action=action,
        params=normalized_params,
    )
    return PatchValidationResult(True, [], normalized_patch, preview)


def _extract_json_payload(text: str) -> str:
    stripped = (text or "").strip()
    fence = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", stripped, flags=re.DOTALL)
    if fence:
        return fence.group(1)
    start = stripped.find("{")
    end = stripped.rfind("}")
    if start == -1 or end == -1 or end < start:
        raise ValueError("structured_healing_json_not_found")
    return stripped[start : end + 1]


def _require_str(raw: dict[str, Any], key: str) -> str:
    value = raw.get(key)
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"structured_healing_{key}_required")
    return value.strip()[:500]


def _normalize_confidence(value: Any) -> float:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return 0.0
    return max(0.0, min(number, 1.0))


def _parse_patch(raw: Any) -> StructuredHealingPatch | None:
    if raw in (None, "", {}):
        return None
    if not isinstance(raw, dict):
        raise ValueError("structured_healing_patch_must_be_object")
    raw_step_index = raw.get("step_index")
    if raw_step_index is None:
        raise ValueError("structured_healing_patch_step_index_required")
    try:
        step_index = int(raw_step_index)
    except (TypeError, ValueError) as exc:
        raise ValueError("structured_healing_patch_step_index_required") from exc
    params = raw.get("params") or {}
    if not isinstance(params, dict):
        raise ValueError("structured_healing_patch_params_must_be_object")
    return StructuredHealingPatch(
        case_type=str(raw.get("case_type") or ""),
        step_index=step_index,
        action=str(raw.get("action") or ""),
        params=params,
    )


def _normalize_case_type(case_type: str) -> str:
    return str(case_type or "").lower().strip()


def _allowlist_for(case_type: str) -> dict[str, set[str]]:
    return WEB_ACTION_PARAM_ALLOWLIST if case_type == "web" else ANDROID_ACTION_PARAM_ALLOWLIST


def _normalize_params(action: str, params: dict[str, Any], allowed_keys: set[str]) -> tuple[dict[str, Any], list[str]]:
    normalized: dict[str, Any] = {}
    reasons: list[str] = []
    for key, value in params.items():
        key_str = str(key)
        lowered = key_str.lower()
        if lowered in _DENIED_PARAM_KEYS or any(token in lowered for token in _DENIED_PARAM_KEYS):
            reasons.append(f"denied_param:{key_str}")
            continue
        if key_str not in allowed_keys:
            reasons.append(f"unsupported_param:{key_str}")
            continue
        if key_str in {"ms", "timeout_ms", "duration"}:
            try:
                value = int(value)
            except (TypeError, ValueError):
                reasons.append(f"invalid_number:{key_str}")
                continue
            value = max(100, min(value, _MAX_WAIT_MS))
        elif isinstance(value, str):
            value = value.strip()
            if len(value) > _MAX_TEXT_PARAM_LENGTH:
                reasons.append(f"param_too_long:{key_str}")
                continue
        elif key_str in {"x", "y", "x1", "y1", "x2", "y2"}:
            try:
                value = int(value)
            except (TypeError, ValueError):
                reasons.append(f"invalid_number:{key_str}")
                continue
        elif not isinstance(value, (bool, int, float, type(None))):
            reasons.append(f"unsupported_value_type:{key_str}")
            continue
        normalized[key_str] = value
    return normalized, reasons
