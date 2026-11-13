"""Pydantic schemas for Android Natural Language Agent domain."""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any, Literal, Optional

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
    terminal_assertions: list[dict[str, Any]] = Field(default_factory=list)
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


# ---- Drafts (A30/A31) ----


class AgentDraftCreateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    restored_initial_state: bool = True


class AgentDraftPatchRequest(BaseModel):
    """编辑草稿必须携带 `expected_version`，服务端据此生成新版本。"""

    model_config = ConfigDict(extra="forbid")

    expected_version: int = Field(..., ge=1)
    steps: Optional[list[dict[str, Any]]] = None
    assertions: Optional[list[dict[str, Any]]] = None
    preconditions: Optional[list[str]] = None


class AgentDraftSummary(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    project_id: int
    session_id: int
    version: int
    schema_version: int
    status: str
    content_hash: str
    blocking_issues: list[dict[str, Any]]
    variables: list[str]
    published_case_id: Optional[int]
    created_at: datetime


class AgentDraftResponse(AgentDraftSummary):
    steps: list[dict[str, Any]]
    assertions: list[dict[str, Any]]
    preconditions: list[str]
    source_map: dict[str, Any]
    environment_snapshot: dict[str, Any]
    published_at: Optional[datetime]


# ---- Replays (A32) ----


class AgentReplayStartRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    initial_state_confirmed: bool
    module_id: int = Field(..., ge=1)
    device_id: Optional[int] = Field(default=None, ge=1)
    idempotency_key: str = Field(..., min_length=1, max_length=128)


class AgentReplayResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    project_id: int
    session_id: int
    draft_id: int
    draft_version: int
    content_hash: str
    status: str
    initial_state_confirmed: bool
    module_id: Optional[int]
    case_id: Optional[int]
    run_id: Optional[int]
    error_code: Optional[str]
    evidence: dict[str, Any]
    started_at: Optional[datetime]
    finished_at: Optional[datetime]
    created_at: datetime


class AgentReplayHandoffResponse(BaseModel):
    replay: AgentReplayResponse
    case_id: int
    run_id: int
    frozen_snapshot: dict[str, Any]


class AgentReplayPreviewItem(BaseModel):
    code: str
    status: str
    message: str


class AgentReplayPreviewResponse(BaseModel):
    draft_id: int
    draft_version: int
    content_hash: str
    ready: bool
    frozen_snapshot: dict[str, Any]
    items: list[AgentReplayPreviewItem]


# ---- Publish (A33) ----


class AgentPublishResponse(BaseModel):
    draft_id: int
    draft_version: int
    case_id: int
    verified_replay_id: int
    published: bool
    idempotent_replay: bool = False


# ---- Loop Run (A22) ----


class AgentRunResultResponse(BaseModel):
    """一次模型循环的收敛结果；只返回稳定状态与用量，不回传模型原文。"""

    status: str
    reason: str
    steps: int = 0
    model_calls: int = 0
    tokens: int = 0


# ---- Completion confirmation (A22) ----


class AgentAssertion(BaseModel):
    """用户确认的终态断言；只有它能让草稿变成可回放。"""

    model_config = ConfigDict(extra="forbid")

    type: Literal["element_visible", "element_absent"]
    resource_id: str = Field(..., min_length=1, max_length=512)


class AgentCompleteRequest(BaseModel):
    """会话收敛请求：finish 只是建议，必须由用户确认终态断言。"""

    model_config = ConfigDict(extra="forbid")

    terminal_assertion_confirmed: bool
    terminal_assertions: list[AgentAssertion] = Field(default_factory=list)
    summary: str = Field(default="", max_length=500)
    outcome: Literal["success", "partial"] = "success"


class AgentVisionModelOut(BaseModel):
    """供工作台选择视觉模型的脱敏只读配置（不暴露密钥与供应商端点）。"""

    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    provider: str
    model_name: str
    enabled: bool
    supports_vision: bool
    description: Optional[str] = None
