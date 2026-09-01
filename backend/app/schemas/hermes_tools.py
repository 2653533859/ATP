"""Contracts for Hermes permission-protected read-only tools."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field, model_validator

from app.schemas.workbench import WorkbenchTaskType


HermesToolName = Literal[
    "failed_tasks",
    "run_detail",
    "quality_trend",
    "requirement_case_links",
    "knowledge_detail",
]
HermesToolStatus = Literal["ok", "empty", "not_found", "timeout", "error"]


class HermesFailedTasksArguments(BaseModel):
    limit: int = Field(default=10, ge=1, le=20)
    task_type: WorkbenchTaskType | None = None

    model_config = {"extra": "forbid"}


class HermesRunDetailArguments(BaseModel):
    task_type: WorkbenchTaskType
    run_id: int = Field(ge=1)

    model_config = {"extra": "forbid"}


class HermesQualityTrendArguments(BaseModel):
    days: int = Field(default=30, ge=1, le=365)
    aggregate: Literal["daily", "weekly"] = "daily"

    model_config = {"extra": "forbid"}


class HermesRequirementCaseLinksArguments(BaseModel):
    requirement_id: int | None = Field(default=None, ge=1)
    case_id: int | None = Field(default=None, ge=1)
    limit: int = Field(default=20, ge=1, le=50)

    @model_validator(mode="after")
    def require_trace_target(self) -> "HermesRequirementCaseLinksArguments":
        if self.requirement_id is None and self.case_id is None:
            raise ValueError("requirement_id 或 case_id 至少填写一个")
        return self

    model_config = {"extra": "forbid"}


class HermesKnowledgeDetailArguments(BaseModel):
    knowledge_id: int = Field(ge=1)

    model_config = {"extra": "forbid"}


HermesToolArguments = (
    HermesFailedTasksArguments
    | HermesRunDetailArguments
    | HermesQualityTrendArguments
    | HermesRequirementCaseLinksArguments
    | HermesKnowledgeDetailArguments
)


class HermesToolCallIn(BaseModel):
    project_id: int = Field(ge=1)
    conversation_id: str = Field(min_length=8, max_length=80, pattern=r"^[A-Za-z0-9._:-]+$")
    tool: HermesToolName
    arguments: dict[str, Any] = Field(default_factory=dict)
    timeout_ms: int = Field(default=3_000, ge=100, le=5_000)

    model_config = {"extra": "forbid"}


class HermesToolDescriptor(BaseModel):
    name: HermesToolName
    description: str
    required_role: Literal["viewer"] = "viewer"
    read_only: Literal[True] = True
    timeout_max_ms: int = Field(ge=100, le=5_000)
    arguments_schema: dict[str, Any] = Field(default_factory=dict)


class HermesToolCatalogOut(BaseModel):
    tools: list[HermesToolDescriptor] = Field(default_factory=list, max_length=10)
    generated_at: datetime


class HermesToolEvidence(BaseModel):
    evidence_id: str
    source_type: Literal["hermes_tool"] = "hermes_tool"
    source_ref: str
    title: str
    excerpt: str
    path: str


class HermesToolOut(BaseModel):
    project_id: int
    conversation_id: str
    tool: HermesToolName
    status: HermesToolStatus
    duration_ms: int = Field(ge=0)
    message: str | None = None
    data: dict[str, Any] = Field(default_factory=dict)
    evidence: list[HermesToolEvidence] = Field(default_factory=list, max_length=50)
    generated_at: datetime
