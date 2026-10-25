from __future__ import annotations

import enum
from typing import Any
from pydantic import BaseModel, Field


class PrecheckStatus(str, enum.Enum):
    PASS = "PASS"
    WARNING = "WARNING"
    FAIL = "FAIL"


class PrecheckScope(str, enum.Enum):
    device = "device"
    platform = "platform"
    app = "app"
    step = "step"
    variable = "variable"
    environment = "environment"


class PrecheckItem(BaseModel):
    scope: PrecheckScope
    status: PrecheckStatus
    code: str
    message: str
    suggestion: str
    step_index: int | None = None
    step_id: str | None = None
    step_action: str | None = None


class AndroidPrecheckSummary(BaseModel):
    total_steps: int = 0
    passed_steps: int = 0
    failed_steps: int = 0
    warning_steps: int = 0
    has_blocking_issue: bool = False


class AndroidPrecheckResponse(BaseModel):
    ok: bool
    device_serial: str | None = None
    platform: str = "android"
    summary: AndroidPrecheckSummary
    items: list[PrecheckItem] = Field(default_factory=list)


class CasePrecheckIn(BaseModel):
    device_serial: str | None = None
    env_id: int | None = None
    extra_vars: dict[str, Any] = Field(default_factory=dict)
    steps: list[dict[str, Any]] | None = None
    config: dict[str, Any] | None = None


class AndroidDraftPrecheckIn(BaseModel):
    project_id: int
    device_serial: str | None = None
    env_id: int | None = None
    extra_vars: dict[str, Any] = Field(default_factory=dict)
    steps: list[dict[str, Any]] | None = None
    config: dict[str, Any] | None = None
