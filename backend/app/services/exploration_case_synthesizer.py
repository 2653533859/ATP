"""Autonomous Exploration Event Sequence to TestCase Synthesizer (Q2.2).

Compresses, de-noises, and synthesizes raw autonomous UI exploration event
sequences into persistent platform TestCase and CaseStep assets.
"""

from __future__ import annotations

import logging
from typing import Any

from app.schemas.case import CaseStepCreate, TestCaseCreate

logger = logging.getLogger(__name__)


def clean_and_compress_events(raw_events: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Clean redundant no-ops, duplicate clicks, and collapse intermediate input events."""
    if not raw_events:
        return []

    compressed: list[dict[str, Any]] = []
    last_action_sig = None

    for ev in raw_events:
        if not isinstance(ev, dict):
            continue

        action_type = str(ev.get("action_type") or "click").lower()
        elem = ev.get("element") or {}
        sig = str(ev.get("action_signature") or f"{action_type}_{elem.get('id')}")

        # Skip consecutive duplicate clicks on the exact same element
        if action_type == "click" and sig == last_action_sig:
            continue

        # If consecutive inputs on the same element, collapse to the latest one
        if action_type == "input" and compressed and compressed[-1].get("action_type") == "input":
            prev_elem = compressed[-1].get("element") or {}
            if prev_elem.get("id") == elem.get("id") and elem.get("id"):
                compressed[-1] = ev
                last_action_sig = sig
                continue

        compressed.append(ev)
        last_action_sig = sig

    return compressed


def synthesize_case_steps(
    events: list[dict[str, Any]],
    platform: str = "android",
) -> tuple[list[CaseStepCreate], list[dict[str, Any]]]:
    """Convert an event stream into human-readable CaseSteps and low-code runner step configs."""
    cleaned = clean_and_compress_events(events)
    case_steps: list[CaseStepCreate] = []
    config_steps: list[dict[str, Any]] = []

    for idx, ev in enumerate(cleaned):
        action_type = str(ev.get("action_type") or "click").lower()
        elem = ev.get("element") or {}
        screen = str(ev.get("screen_name") or "当前界面")
        next_screen = str(ev.get("next_screen") or "")

        step_no = idx + 1
        elem_id = str(elem.get("id") or elem.get("resource_id") or elem.get("accessibility_id") or "").strip()
        elem_text = str(elem.get("text") or elem.get("title") or "").strip()

        # Strategy selection: id > text > xpath/bounds
        strategy = "id" if elem_id else ("accessibility_id" if platform == "ios" else "text")
        val = elem_id or elem_text or str(elem.get("tag") or "unknown")

        if action_type == "click":
            readable_target = f"点击控件 [{elem_text or elem_id or '控件'}]"
            step_action = "click"
            test_data = f"{strategy}={val}"
            expected = f"响应点击，流转至 {next_screen}" if next_screen else "响应点击"
            runner_step = {
                "action": "click",
                "name": readable_target,
                "params": {"strategy": strategy, "value": val},
            }

        elif action_type == "input":
            input_val = str(ev.get("input_text") or elem.get("sample_text") or "test_input")
            readable_target = f"在 [{elem_text or elem_id or '输入框'}] 输入文本: {input_val}"
            step_action = "input"
            test_data = input_val
            expected = "文本输入完成"
            runner_step = {
                "action": "input",
                "name": readable_target,
                "params": {"strategy": strategy, "value": val, "text": input_val},
            }

        elif action_type == "back":
            readable_target = "返回上级界面"
            step_action = "back"
            test_data = None
            expected = "返回上级页面"
            runner_step = {"action": "back", "name": readable_target, "params": {}}

        elif action_type == "swipe":
            readable_target = "屏幕滑动操作"
            step_action = "swipe"
            test_data = None
            expected = "滑动完成"
            runner_step = {
                "action": "swipe",
                "name": readable_target,
                "params": ev.get("params") or {"x": 500, "y": 1500, "to_x": 500, "to_y": 500},
            }

        else:
            readable_target = f"执行操作: {action_type}"
            step_action = action_type
            test_data = None
            expected = "操作执行成功"
            runner_step = {"action": action_type, "name": readable_target, "params": ev.get("params") or {}}

        case_steps.append(
            CaseStepCreate(
                step_no=step_no,
                action=step_action,
                test_data=test_data,
                expected_result=expected,
                is_key_step=idx == len(cleaned) - 1,  # Last step is key step
                remarks=f"由探索事件序列在 {screen} 自动合成",
            )
        )
        config_steps.append(runner_step)

    # Automatically synthesize a final verification step if target screen known
    if cleaned and cleaned[-1].get("next_screen"):
        final_screen = str(cleaned[-1].get("next_screen"))
        step_no = len(case_steps) + 1
        case_steps.append(
            CaseStepCreate(
                step_no=step_no,
                action="assert_text",
                test_data=final_screen,
                expected_result=f"页面包含文本或标题: {final_screen}",
                is_key_step=True,
                remarks="自动合成的目标页面终态校验",
            )
        )
        config_steps.append(
            {
                "action": "assert_text",
                "name": f"终态校验: {final_screen}",
                "params": {"text": final_screen},
            }
        )

    return case_steps, config_steps


def synthesize_test_case_payload(
    name: str,
    module_id: int,
    events: list[dict[str, Any]],
    *,
    case_type: str = "android",
    description: str | None = None,
    platform: str = "android",
) -> TestCaseCreate:
    """Synthesize a complete TestCaseCreate schema instance from exploration events."""
    case_steps, config_steps = synthesize_case_steps(events, platform=platform)

    return TestCaseCreate(
        name=name.strip(),
        description=description or f"由 AI 智能探索遍历自动合成，覆盖 {len(events)} 项原始事件。",
        summary=f"智能探索合成用例 ({len(case_steps)} 步骤)",
        case_type=case_type,  # type: ignore[arg-type]
        module_id=module_id,
        tags=["ai_synthesized", "autonomous_exploration"],
        priority="P2",
        case_level="regression",
        steps=case_steps,
        config={"steps": config_steps, "platform": platform},
        automation_status="auto",
    )
