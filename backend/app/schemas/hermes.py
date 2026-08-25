"""Contracts for the project-scoped Hermes retrieval assistant."""

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field, field_validator


HermesSourceType = Literal["knowledge", "requirement", "case"]


class HermesQueryIn(BaseModel):
    project_id: int = Field(ge=1)
    query: str = Field(min_length=1, max_length=2_000)
    limit: int = Field(default=8, ge=1, le=20)

    @field_validator("query")
    @classmethod
    def trim_query(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("查询内容不能为空")
        return value


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
    mode: Literal["project_retrieval", "no_results"]
    answer: str
    sources: list[HermesSourceOut] = Field(default_factory=list, max_length=20)
    generated_at: datetime
