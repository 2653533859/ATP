"""Pydantic schemas for Android Natural Language Agent domain."""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any, Optional

from pydantic import BaseModel, ConfigDict, Field


class AgentSessionStatus(str, Enum):
    created = "created"
    prechecking = "prechecking"
    running = "running"
    pause_requested = "pause_requested"
    paused = "paused"
    completed = "completed"
    failed = "failed"
    cancelled = "cancelled"


class AgentController(str, Enum):
    agent = "agent"
    manual = "manual"
    none = "none"


class AgentControlAction(str, Enum):
    pause = "pause"
    takeover = "takeover"
    resume = "resume"
    cancel = "cancel"


class AgentErrorCode(str, Enum):
    device_busy = "device_busy"
    device_offline = "device_offline"
    package_out_of_scope = "package_out_of_scope"
    model_capability_missing = "model_capability_missing"
    observation_stale = "observation_stale"
    observation_unavailable = "observation_unavailable"
    target_ambiguous = "target_ambiguous"
    target_unavailable = "target_unavailable"
    lease_lost = "lease_lost"
    action_blocked = "action_blocked"
    outcome_unknown = "outcome_unknown"
    budget_exceeded = "budget_exceeded"
    control_epoch_changed = "control_epoch_changed"
    write_cancelled = "write_cancelled"
    system_restarted_needs_review = "system_restarted_needs_review"
    version_conflict = "version_conflict"


# ---- Session Configuration & Lifecycle ----


class AgentBudgetConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    max_steps: int = Field(default=30, ge=1, le=100)
    max_calls: int = Field(default=40, ge=1, le=120)
    max_duration_seconds: int = Field(default=600, ge=60, le=1800)


class AgentSessionCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    device_id: int
    package_name: str = Field(..., min_length=1, max_length=128)
    goal: str = Field(..., min_length=1, max_length=1000)
    expected_outcome: str = Field(..., min_length=1, max_length=1000)
    title: str = Field(default="Android Agent Session", max_length=128)
    llm_config_id: Optional[int] = None
    context_values: dict[str, str] = Field(default_factory=dict)
    budget: AgentBudgetConfig = Field(default_factory=AgentBudgetConfig)


class AgentSessionResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    project_id: int
    device_id: Optional[int]
    created_by: Optional[int]
    title: str
    goal: str
    expected_outcome: str
    package_name: str
    llm_config_id: Optional[int]
    status: str
    controller: str
    version: int
    control_epoch: int
    lease_token: Optional[str]
    budget_max_steps: int
    budget_max_calls: int
    steps_count: int
    model_calls_count: int
    total_tokens: int
    error_code: Optional[str]
    context_values: dict[str, Any]
    started_at: Optional[datetime]
    finished_at: Optional[datetime]
    created_at: datetime
    updated_at: datetime


# ---- Control & Manual Actions ----


class AgentControlRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    action: AgentControlAction
    reason: Optional[str] = Field(default=None, max_length=256)
    expected_version: Optional[int] = Field(default=None)


class AgentControlResponse(BaseModel):
    session_id: int
    status: str
    controller: str
    control_epoch: int
    version: int
    message: str


class AgentManualActionRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    action: str = Field(..., pattern=r"^(tap|input|back|wait|swipe)$")
    params: dict[str, Any] = Field(default_factory=dict)
    idempotency_key: Optional[str] = Field(default=None, max_length=64)
    reason: Optional[str] = Field(default=None, max_length=256)


# ---- Event Stream ----


class AgentEventItem(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    session_id: int
    seq: int
    event_type: str
    payload: dict[str, Any]
    artifact_refs: list[str]
    created_at: datetime


class AgentEventsResponse(BaseModel):
    items: list[AgentEventItem]
    next_seq: int
    has_more: bool
