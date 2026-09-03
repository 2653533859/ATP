from __future__ import annotations

from datetime import datetime
from typing import Any, Literal
from uuid import uuid4

from pydantic import BaseModel, Field, field_validator

from app.schemas.hermes_tools import HermesToolEvidence, HermesToolName, HermesToolStatus


HermesOrchestrationStatus = Literal["matched", "no_match", "needs_input", "cancelled"]


class HermesOrchestrationIn(BaseModel):
    project_id: int = Field(ge=1)
    query: str = Field(min_length=1, max_length=2_000)
    conversation_id: str = Field(
        default_factory=lambda: f"hermes-{uuid4().hex}",
        min_length=8,
        max_length=80,
        pattern=r"^[A-Za-z0-9._:-]+$",
    )
    session_id: int | None = Field(default=None, ge=1)

    @field_validator("query")
    @classmethod
    def trim_query(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("查询内容不能为空")
        return value

    @field_validator("conversation_id", mode="before")
    @classmethod
    def trim_conversation_id(cls, value: object) -> object:
        return value.strip() if isinstance(value, str) else value

    model_config = {"extra": "forbid"}


class HermesOrchestrationPlanOut(BaseModel):
    tool: HermesToolName
    arguments: dict[str, Any] = Field(default_factory=dict)
    reason: str


class HermesOrchestrationStepOut(BaseModel):
    tool: HermesToolName
    arguments: dict[str, Any] = Field(default_factory=dict)
    status: HermesToolStatus
    duration_ms: int = Field(ge=0)
    message: str | None = None
    data: dict[str, Any] = Field(default_factory=dict)
    evidence: list[HermesToolEvidence] = Field(default_factory=list, max_length=50)


class HermesOrchestrationOut(BaseModel):
    project_id: int
    conversation_id: str
    query: str
    status: HermesOrchestrationStatus
    clarification: str | None = None
    plans: list[HermesOrchestrationPlanOut] = Field(default_factory=list, max_length=2)
    steps: list[HermesOrchestrationStepOut] = Field(default_factory=list, max_length=2)
    answer: str
    generated_at: datetime
    session_id: int | None = None
    message_index: int | None = None
