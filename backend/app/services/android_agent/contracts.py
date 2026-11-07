"""Strict, non-executing model decision contract for the M0 probe."""

from __future__ import annotations

from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, TypeAdapter

Identifier = Annotated[str, StringConstraints(pattern=r"^[A-Za-z0-9_.:-]{1,128}$")]
VariableRef = Annotated[str, StringConstraints(pattern=r"^[A-Za-z_][A-Za-z0-9_]{0,63}$")]
NonEmpty = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=512)]


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)


class ExpectedElement(StrictModel):
    type: Literal["element_visible", "element_absent"]
    resource_id: NonEmpty


class NodeTarget(StrictModel):
    node_id: Identifier


class DecisionBase(StrictModel):
    schema_version: Literal[1]
    observation_id: Identifier
    reason: NonEmpty


class Tap(DecisionBase):
    action: Literal["tap"]
    target: NodeTarget
    expected_observation: ExpectedElement


class Input(DecisionBase):
    action: Literal["input"]
    target: NodeTarget
    value_ref: VariableRef
    expected_observation: ExpectedElement


class Swipe(DecisionBase):
    action: Literal["swipe"]
    direction: Literal["up", "down", "left", "right"]
    distance_fraction: Annotated[float, Field(gt=0, le=0.8, allow_inf_nan=False)]
    expected_observation: ExpectedElement


class Back(DecisionBase):
    action: Literal["back"]
    expected_observation: ExpectedElement


class Wait(DecisionBase):
    action: Literal["wait"]
    timeout_ms: Annotated[int, Field(ge=100, le=15000)]
    expected_observation: ExpectedElement


class Finish(DecisionBase):
    action: Literal["finish"]


class RequestHelp(DecisionBase):
    action: Literal["request_help"]
    code: Literal["target_ambiguous", "sensitive_page", "unsupported_page", "cannot_progress"]


Decision = Annotated[Tap | Input | Swipe | Back | Wait | Finish | RequestHelp, Field(discriminator="action")]
DECISION_ADAPTER: TypeAdapter[Decision] = TypeAdapter(Decision)


class DecisionRejected(ValueError):
    """Only a stable error code is exposed; never echo model text or secrets."""


def parse_decision(raw: str) -> Decision:
    """Accept one plain JSON object, not Markdown, tool code, or repaired JSON."""
    try:
        size = len(raw.encode("utf-8"))
    except UnicodeEncodeError:
        raise DecisionRejected("invalid_decision") from None
    if size > 16384:
        raise DecisionRejected("response_too_large")
    # Python's JSON parser can reject duplicate fields; accepting last-wins
    # would make the policy inspect a different command than an upstream parser.
    import json

    def unique_pairs(pairs):
        obj = {}
        for key, value in pairs:
            if key in obj:
                raise ValueError("duplicate_key")
            obj[key] = value
        return obj

    try:
        data = json.loads(raw, object_pairs_hook=unique_pairs)
        if not isinstance(data, dict) or type(data.get("schema_version")) is not int:
            raise ValueError("invalid_schema_version")
        return DECISION_ADAPTER.validate_python(data)
    except (ValueError, RecursionError):
        raise DecisionRejected("invalid_decision") from None


def validate_context(
    decision: Decision,
    *,
    observation_id: str,
    observed_package: str,
    allowed_package: str,
    captured_epoch: int,
    current_epoch: int,
    controllable_node_ids: set[str],
    allowed_value_refs: set[str],
    device_online: bool,
    observation_available: bool,
) -> None:
    """POC validation only; does not acquire a lease or authorize execution."""
    if captured_epoch != current_epoch:
        raise DecisionRejected("control_epoch_changed")
    if decision.observation_id != observation_id:
        raise DecisionRejected("observation_stale")
    if not isinstance(decision, RequestHelp):
        if not device_online:
            raise DecisionRejected("device_offline")
        if not observation_available:
            raise DecisionRejected("observation_unavailable")
    if not allowed_package or observed_package != allowed_package:
        raise DecisionRejected("package_out_of_scope")
    if isinstance(decision, (Tap, Input)) and decision.target.node_id not in controllable_node_ids:
        raise DecisionRejected("target_unavailable")
    if isinstance(decision, Input) and decision.value_ref not in allowed_value_refs:
        raise DecisionRejected("value_ref_forbidden")
