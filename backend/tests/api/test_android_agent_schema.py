"""Tests for Android Agent Pydantic schemas, validation and error codes."""

import pytest
from pydantic import ValidationError

from app.schemas.android_agent import (
    AgentBudgetConfig,
    AgentControlAction,
    AgentControlRequest,
    AgentErrorCode,
    AgentEventsResponse,
    AgentManualActionRequest,
    AgentSessionCreate,
    AgentSessionStatus,
)


def test_agent_session_create_valid():
    data = {
        "device_id": 1,
        "package_name": "com.example.shop",
        "goal": "Search sneakers and checkout",
        "expected_outcome": "Payment page is visible",
        "context_values": {"user": "tester"},
        "budget": {"max_steps": 25, "max_calls": 35, "max_duration_seconds": 300},
    }
    payload = AgentSessionCreate(**data)
    assert payload.device_id == 1
    assert payload.package_name == "com.example.shop"
    assert payload.budget.max_steps == 25
    assert payload.budget.max_calls == 35


def test_agent_session_create_rejects_empty_goal():
    with pytest.raises(ValidationError):
        AgentSessionCreate(
            device_id=1,
            package_name="com.example.shop",
            goal="",
            expected_outcome="Success",
        )


def test_agent_session_create_budget_bounds():
    with pytest.raises(ValidationError):
        # max_steps > 100
        AgentBudgetConfig(max_steps=150)

    with pytest.raises(ValidationError):
        # max_calls < 1
        AgentBudgetConfig(max_calls=0)

    with pytest.raises(ValidationError):
        # duration < 60
        AgentBudgetConfig(max_duration_seconds=30)


def test_agent_control_request_action_enum():
    req = AgentControlRequest(action=AgentControlAction.pause, reason="User clicked pause")
    assert req.action == AgentControlAction.pause
    assert req.reason == "User clicked pause"

    with pytest.raises(ValidationError):
        AgentControlRequest.model_validate({"action": "invalid_action"})


def test_agent_manual_action_regex():
    req = AgentManualActionRequest(action="tap", params={"x": 100, "y": 200})
    assert req.action == "tap"

    with pytest.raises(ValidationError):
        # shell 命令必须被 pattern 严格拒绝
        AgentManualActionRequest(action="shell", params={"command": "reboot"})


def test_agent_error_codes_completeness():
    assert AgentErrorCode.device_busy.value == "device_busy"
    assert AgentErrorCode.outcome_unknown.value == "outcome_unknown"
    assert AgentErrorCode.control_epoch_changed.value == "control_epoch_changed"
    assert AgentSessionStatus.running.value == "running"
    assert AgentSessionStatus.pause_requested.value == "pause_requested"


def test_agent_events_response():
    resp = AgentEventsResponse(
        items=[
            {
                "id": 1,
                "session_id": 10,
                "seq": 1,
                "event_type": "session_created",
                "payload": {"goal": "test"},
                "artifact_refs": [],
                "created_at": "2026-11-10T10:00:00Z",
            }
        ],
        next_seq=2,
        has_more=False,
    )
    assert len(resp.items) == 1
    assert resp.next_seq == 2
    assert not resp.has_more
