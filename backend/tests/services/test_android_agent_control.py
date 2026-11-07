import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest

from app.models.bootstrap import load_all_models
from app.services.ai_case.llm_client import LLMRequest
from app.services.android_agent.contracts import parse_decision
from app.services.android_agent.control import ControlRejected, ControlState, DeviceControlGate
from app.services.android_agent.device_adapter import AndroidDeviceAdapter, DeviceAdapterError, UiTarget
from app.services.android_agent.single_step import StepBudget, run_model_step

load_all_models()

TREE = (
    '<hierarchy><node resource-id="a:id/go" text="go" class="android.widget.Button" enabled="true" '
    'clickable="true" password="false" bounds="[0,0][10,10]" /></hierarchy>'
)


class Transport:
    def __init__(self):
        self.calls = []

    def current_package(self):
        return "a"

    def rpc_once(self, method, params):
        self.calls.append(method)
        return {"dumpWindowHierarchy": TREE, "count": 1, "click": True}.get(method, True)


def adapter(transport=None):
    return AndroidDeviceAdapter(transport or Transport(), package="a", width=100, height=100)


def decision():
    return parse_decision(
        '{"schema_version":1,"observation_id":"o1","reason":"r","action":"tap","target":{"node_id":"n1"},'
        '"expected_observation":{"type":"element_visible","resource_id":"a:id/go"}}'
    )


def test_empty_target_is_rejected():
    with pytest.raises(DeviceAdapterError, match="empty_target"):
        UiTarget()


@pytest.mark.parametrize("target", [UiTarget("a:id/missing"), UiTarget(text="g")])
def test_wait_for_times_out_and_never_substring_matches(target):
    now = [0.0]

    def sleep(seconds):
        now[0] += seconds

    with pytest.raises(DeviceAdapterError, match="condition_timeout"):
        adapter().wait_for(target, timeout_ms=500, clock=lambda: now[0], sleep=sleep)


def test_tap_gate_rejection_prevents_dispatch():
    transport = Transport()

    def deny():
        raise ControlRejected("lease_lost")

    with pytest.raises(ControlRejected):
        adapter(transport).tap(UiTarget("a:id/go"), assert_write_allowed=deny)
    assert "click" not in transport.calls


def test_tap_error_after_dispatch_is_unknown_and_not_retried():
    transport = Transport()
    original = transport.rpc_once

    def failing(method, params):
        if method == "click":
            transport.calls.append(method)
            raise OSError("boom")
        return original(method, params)

    transport.rpc_once = failing
    with pytest.raises(DeviceAdapterError, match="write_outcome_unknown"):
        adapter(transport).tap(UiTarget("a:id/go"), assert_write_allowed=lambda: None)
    assert transport.calls.count("click") == 1


class _Db:
    async def __aenter__(self):
        return self

    async def __aexit__(self, *_):
        return False


def gate(state):
    return DeviceControlGate(_Db, device_id=1, lease_token="t", state=state)


def run_step(transport, state, budget=None, probe=None):
    probe = probe or AsyncMock(return_value=SimpleNamespace(decision=decision(), usage={"total_tokens": 7}))
    request = LLMRequest(provider="openai", api_key="k", model_name="m", prompt="")
    with (
        patch("app.services.android_agent.single_step.probe_model", probe),
        patch("app.services.android_agent.control.get_active_device_lease", AsyncMock(return_value=object())),
    ):
        return asyncio.run(
            run_model_step(
                adapter(transport),
                request,
                goal="g",
                observation_id="o1",
                gate=gate(state),
                budget=budget or StepBudget(),
            )
        )


def test_step_acts_once_and_counts_usage():
    transport, budget = Transport(), StepBudget()
    outcome = run_step(transport, ControlState(), budget)
    assert (outcome.status, outcome.code) == ("acted", "expectation_met")
    assert transport.calls.count("click") == 1
    assert (budget.model_calls, budget.actions, budget.total_tokens) == (1, 1, 7)


def test_late_model_response_is_rejected_after_pause():
    transport, state = Transport(), ControlState()

    async def late(*_, **__):
        state.pause()
        return SimpleNamespace(decision=decision(), usage={})

    outcome = run_step(transport, state, probe=late)
    assert (outcome.status, outcome.code) == ("halted", "control_epoch_changed")
    assert "click" not in transport.calls


def test_budget_exhaustion_stops_before_model_call():
    probe = AsyncMock()
    outcome = run_step(Transport(), ControlState(), StepBudget(max_model_calls=0), probe)
    assert outcome.code == "budget_exceeded"
    probe.assert_not_called()


def test_finish_is_not_success():
    finish = parse_decision('{"schema_version":1,"observation_id":"o1","reason":"r","action":"finish"}')
    transport = Transport()
    probe = AsyncMock(return_value=SimpleNamespace(decision=finish, usage={}))
    outcome = run_step(transport, ControlState(), probe=probe)
    assert outcome.status == "needs_review"
    assert "click" not in transport.calls


def test_gate_detects_lost_lease_and_cancel():
    with patch("app.services.android_agent.control.get_active_device_lease", AsyncMock(return_value=None)):
        with pytest.raises(ControlRejected, match="lease_lost"):
            asyncio.run(gate(ControlState()).check(0))
    state = ControlState()
    state.cancel()
    with pytest.raises(ControlRejected, match="write_cancelled"):
        asyncio.run(gate(state).check(1))
