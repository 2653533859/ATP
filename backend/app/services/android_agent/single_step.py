"""M0 one-step loop: observe, ask the model, revalidate, act once, verify.

A halted outcome never retries a write; `finish` is never treated as success.
"""

from __future__ import annotations

import asyncio
from concurrent.futures import TimeoutError as FutureTimeoutError
from dataclasses import asdict, dataclass, field
import time

from app.services.ai_case.llm_client import LLMRequest
from app.services.android_agent.contracts import (
    Back,
    Decision,
    DecisionRejected,
    ExpectedElement,
    Finish,
    Input,
    RequestHelp,
    Swipe,
    Tap,
    Wait,
    validate_context,
)
from app.services.android_agent.control import ControlRejected, DeviceControlGate
from app.services.android_agent.device_adapter import AndroidDeviceAdapter, DeviceAdapterError, UiTarget
from app.services.android_agent.model_probe import probe_model
from app.services.android_agent.observation import UiNode


@dataclass
class StepBudget:
    max_model_calls: int = 40
    max_actions: int = 30
    deadline: float = field(default_factory=lambda: time.monotonic() + 600)
    model_calls: int = 0
    actions: int = 0
    total_tokens: int = 0

    def exhausted(self) -> bool:
        return (
            self.model_calls >= self.max_model_calls
            or self.actions >= self.max_actions
            or time.monotonic() >= self.deadline
        )


@dataclass(frozen=True)
class StepOutcome:
    status: str  # acted | needs_review | halted
    code: str
    decision: Decision | None = None


def _target(node: UiNode) -> UiTarget:
    # Text is only part of the selector when it is complete and identifying.
    text = node.text if node.text and not node.text_truncated else ""
    return UiTarget(node.resource_id, text)


def _expected(adapter: AndroidDeviceAdapter, expected: ExpectedElement, timeout_ms: int) -> None:
    adapter.wait_for(
        UiTarget(resource_id=expected.resource_id), timeout_ms=timeout_ms, absent=expected.type == "element_absent"
    )


async def run_model_step(
    adapter: AndroidDeviceAdapter,
    request: LLMRequest,
    *,
    goal: str,
    observation_id: str,
    gate: DeviceControlGate,
    budget: StepBudget,
    values: dict[str, str] | None = None,
) -> StepOutcome:
    """`request` carries the caller-authorized screenshot of this same observation."""
    if budget.exhausted():
        return StepOutcome("halted", "budget_exceeded")
    captured_epoch = gate.state.epoch
    values = values or {}
    try:
        nodes = await asyncio.to_thread(adapter.observe)
    except DeviceAdapterError as exc:
        return StepOutcome("halted", str(exc))
    observation = {
        "observation_id": observation_id,
        "package_name": adapter.package,
        "allowed_value_refs": sorted(values),
        "nodes": [
            {key: value for key, value in asdict(node).items() if key not in {"parent_id", "redacted"}}
            for node in nodes
        ],
    }
    budget.model_calls += 1
    try:
        result = await probe_model(request, goal=goal, observation=observation)
    except DecisionRejected as exc:
        return StepOutcome("halted", str(exc))
    budget.total_tokens += result.usage.get("total_tokens", 0)
    decision = result.decision
    by_id = {node.node_id: node for node in nodes}
    try:
        validate_context(
            decision,
            observation_id=observation_id,
            observed_package=adapter.package,
            allowed_package=adapter.package,
            captured_epoch=captured_epoch,
            current_epoch=gate.state.epoch,
            controllable_node_ids={n.node_id for n in nodes if n.enabled and n.bounds and not n.redacted},
            allowed_value_refs=set(values),
            device_online=True,
            observation_available=True,
        )
    except DecisionRejected as exc:
        return StepOutcome("halted", str(exc), decision)
    if isinstance(decision, Finish):
        return StepOutcome("needs_review", "finish_proposed", decision)
    if isinstance(decision, RequestHelp):
        return StepOutcome("needs_review", decision.code, decision)
    if budget.actions >= budget.max_actions:
        return StepOutcome("halted", "budget_exceeded", decision)

    allow = gate.sync_check(captured_epoch, asyncio.get_running_loop())
    try:
        if isinstance(decision, Tap):
            budget.actions += 1
            await asyncio.to_thread(adapter.tap, _target(by_id[decision.target.node_id]), assert_write_allowed=allow)
        elif isinstance(decision, Input):
            budget.actions += 1
            await asyncio.to_thread(
                adapter.replace_text,
                by_id[decision.target.node_id].resource_id,
                values[decision.value_ref],
                assert_write_allowed=allow,
            )
        elif isinstance(decision, Swipe):
            budget.actions += 1
            await asyncio.to_thread(
                adapter.swipe,
                decision.direction,
                decision.distance_fraction,
                assert_write_allowed=allow,
            )
        elif isinstance(decision, Back):
            budget.actions += 1
            await asyncio.to_thread(adapter.press_back, assert_write_allowed=allow)
        timeout_ms = decision.timeout_ms if isinstance(decision, Wait) else 10000
        await asyncio.to_thread(_expected, adapter, decision.expected_observation, timeout_ms)
    except (ControlRejected, DeviceAdapterError) as exc:
        return StepOutcome("halted", str(exc), decision)
    except (FutureTimeoutError, TimeoutError):
        # The gate could not answer in time, so the write was not dispatched.
        return StepOutcome("halted", "control_check_timeout", decision)
    return StepOutcome("acted", "expectation_met", decision)
