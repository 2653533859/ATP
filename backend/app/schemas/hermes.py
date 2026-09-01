"""Contracts for the project-scoped Hermes retrieval assistant."""

import json
from datetime import date, datetime
from typing import Literal
from uuid import uuid4

from pydantic import BaseModel, Field, field_validator, model_validator


HermesSourceType = Literal["knowledge", "requirement", "case"]
HermesMessageRole = Literal["user", "assistant"]


class HermesHistoryItem(BaseModel):
    role: HermesMessageRole
    content: str = Field(min_length=1, max_length=2_000)

    @field_validator("content")
    @classmethod
    def trim_content(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("对话内容不能为空")
        return value


class HermesQueryIn(BaseModel):
    project_id: int = Field(ge=1)
    query: str = Field(min_length=1, max_length=2_000)
    limit: int = Field(default=8, ge=1, le=20)
    conversation_id: str = Field(
        default_factory=lambda: f"hermes-{uuid4().hex}",
        min_length=8,
        max_length=80,
        pattern=r"^[A-Za-z0-9._:-]+$",
    )
    history: list[HermesHistoryItem] = Field(default_factory=list, max_length=12)
    source_types: list[HermesSourceType] = Field(default_factory=list, max_length=3)
    updated_from: date | None = None
    updated_to: date | None = None
    context_budget: int = Field(default=6_000, ge=1_000, le=12_000)
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

    @field_validator("source_types")
    @classmethod
    def normalize_source_types(cls, values: list[HermesSourceType]) -> list[HermesSourceType]:
        return list(dict.fromkeys(values))

    @model_validator(mode="after")
    def validate_date_range(self) -> "HermesQueryIn":
        if self.updated_from and self.updated_to and self.updated_from > self.updated_to:
            raise ValueError("更新时间范围无效")
        return self


class HermesSourceOut(BaseModel):
    source_type: HermesSourceType
    source_id: int
    project_id: int | None = None
    title: str
    excerpt: str
    source_ref: str | None = None
    path: str
    match_terms: list[str] = Field(default_factory=list)
    match_score: int = Field(ge=0)
    updated_at: datetime | None = None


class HermesQueryOut(BaseModel):
    project_id: int
    query: str
    conversation_id: str
    history_used: int = Field(ge=0)
    history_omitted: int = Field(ge=0)
    context_chars: int = Field(ge=0)
    context_budget: int = Field(ge=1_000, le=12_000)
    source_types: list[HermesSourceType] = Field(default_factory=list, max_length=3)
    updated_from: date | None = None
    updated_to: date | None = None
    mode: Literal["llm_grounded", "project_retrieval", "no_results"]
    answer: str
    sources: list[HermesSourceOut] = Field(default_factory=list, max_length=20)
    generated_at: datetime
    session_id: int
    message_index: int
    prompt_version: str = "hermes-v2"
    latency_ms: int = Field(ge=0)


class HermesSessionOut(BaseModel):
    id: int
    project_id: int
    title: str
    context_filters: dict
    messages: list[dict]
    drafts: list[dict]
    metrics: dict
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class HermesSessionCreateIn(BaseModel):
    project_id: int = Field(ge=1)
    title: str = Field(default="Hermes 会话", max_length=80)

    @field_validator("title")
    @classmethod
    def trim_title(cls, value: str) -> str:
        return value.strip() or "Hermes 会话"


class HermesEvaluationQuestionOut(BaseModel):
    id: str
    prompt: str
    expected_mode: Literal["llm_grounded", "project_retrieval", "no_results"]


class HermesEvaluationSetOut(BaseModel):
    id: str
    version: str
    questions: list[HermesEvaluationQuestionOut] = Field(default_factory=list, max_length=20)


class HermesEvaluationSetMetaOut(BaseModel):
    id: str
    version: str
    size: int = Field(ge=0)


class HermesCostTrackingOut(BaseModel):
    available: bool
    reason: str


class HermesGovernanceSummaryOut(BaseModel):
    prompt_version: str
    prompt_versions: list[str] = Field(default_factory=list, max_length=20)
    evaluation_set: HermesEvaluationSetMetaOut
    sessions: int = Field(ge=0)
    assistant_messages: int = Field(ge=0)
    citation_coverage: float = Field(ge=0, le=1)
    refusal_rate: float = Field(ge=0, le=1)
    no_result_rate: float = Field(ge=0, le=1)
    helpful_count: int = Field(ge=0)
    not_helpful_count: int = Field(ge=0)
    feedback_total: int = Field(ge=0)
    helpful_rate: float | None = Field(default=None, ge=0, le=1)
    average_latency_ms: int = Field(ge=0)
    p95_latency_ms: int = Field(ge=0)
    cost_tracking: HermesCostTrackingOut


class HermesToolIn(BaseModel):
    project_id: int = Field(ge=1)
    arguments: dict = Field(default_factory=dict)


class HermesDraftIn(BaseModel):
    project_id: int = Field(ge=1)
    draft_type: Literal["test_plan"] = "test_plan"
    payload: dict
    sources: list[dict] = Field(default_factory=list, max_length=20)

    @field_validator("payload")
    @classmethod
    def bound_payload(cls, value: dict) -> dict:
        if len(json.dumps(value, ensure_ascii=False, default=str).encode("utf-8")) > 64 * 1024:
            raise ValueError("Hermes 草稿不能超过 64KB")
        return value


class HermesDraftConfirmIn(BaseModel):
    project_id: int = Field(ge=1)
    draft_id: str = Field(min_length=1, max_length=64)
    confirmation: Literal["CONFIRM"]


class HermesFeedbackIn(BaseModel):
    project_id: int = Field(ge=1)
    message_index: int = Field(ge=0)
    rating: Literal["helpful", "not_helpful"]
    comment: str | None = Field(default=None, max_length=1000)
