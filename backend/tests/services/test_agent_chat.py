"""Unit tests for unified Hermes agent chat helpers."""

from __future__ import annotations

from app.services.ai_case.agent_chat import (
    build_agent_system_prompt,
    extract_completed_proposal,
    parse_action_proposal,
    split_stream_action_tag,
)


def test_split_stream_action_tag_handles_partial_and_full_tag() -> None:
    emit, rem, inside = split_stream_action_tag("分析完成[[ACT")
    assert emit == "分析完成"
    assert rem == "[[ACT"
    assert inside is False

    emit2, rem2, inside2 = split_stream_action_tag(rem + 'ION_PROPOSAL]]{"action":"run_case","params":{"case_id":5}}')
    assert emit2 == ""
    assert rem2.startswith("[[ACTION_PROPOSAL]]")
    assert inside2 is True


def test_extract_completed_proposal_parses_valid_action() -> None:
    raw = '[[ACTION_PROPOSAL]]{"action":"create_case","title":"创建登录用例","summary":"Web 用例","params":{"name":"登录","case_type":"web"}}[[/ACTION_PROPOSAL]]'
    parsed = extract_completed_proposal(raw)
    assert parsed is not None
    assert parsed["action"] == "create_case"
    assert parsed["params"]["name"] == "登录"


def test_parse_action_proposal_rejects_disallowed_action() -> None:
    assert parse_action_proposal('{"action":"drop_database","params":{}}') is None


def test_parse_action_proposal_accepts_extended_actions() -> None:
    for action in ("run_suite", "update_case", "update_defect"):
        parsed = parse_action_proposal(f'{{"action":"{action}","title":"{action}","params":{{"id":1}}}}')
        assert parsed is not None
        assert parsed["action"] == action


def test_build_agent_system_prompt_reflects_project_presence() -> None:
    assert "ACTION_PROPOSAL" not in build_agent_system_prompt(False)
    assert "ACTION_PROPOSAL" in build_agent_system_prompt(True)
