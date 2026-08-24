"""Contracts for the project-aware knowledge hub."""

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field, field_validator


KnowledgeSourceType = Literal[
    "standard",
    "defect",
    "solution",
    "runbook",
    "experience",
    "requirement",
    "execution",
]
KnowledgeStatus = Literal["draft", "published", "archived"]


class KnowledgeCreate(BaseModel):
    project_id: int | None = Field(default=None, ge=1)
    source_type: KnowledgeSourceType = "experience"
    title: str = Field(min_length=1, max_length=256)
    summary: str | None = Field(default=None, max_length=2_000)
    content: str = Field(min_length=1, max_length=50_000)
    source_ref: str | None = Field(default=None, max_length=512)
    tags: list[str] = Field(default_factory=list, max_length=20)
    status: KnowledgeStatus = "draft"

    @field_validator("title", "content")
    @classmethod
    def trim_required_text(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("知识标题和正文不能为空")
        return value

    @field_validator("summary", "source_ref")
    @classmethod
    def trim_optional_text(cls, value: str | None) -> str | None:
        return value.strip() if value and value.strip() else None

    @field_validator("tags")
    @classmethod
    def normalize_tags(cls, values: list[str]) -> list[str]:
        return list(dict.fromkeys(value.strip() for value in values if value and value.strip()))[:20]


class KnowledgeUpdate(BaseModel):
    source_type: KnowledgeSourceType | None = None
    title: str | None = Field(default=None, min_length=1, max_length=256)
    summary: str | None = Field(default=None, max_length=2_000)
    content: str | None = Field(default=None, min_length=1, max_length=50_000)
    source_ref: str | None = Field(default=None, max_length=512)
    tags: list[str] | None = Field(default=None, max_length=20)
    status: KnowledgeStatus | None = None

    @field_validator("title", "content")
    @classmethod
    def trim_optional_required_text(cls, value: str | None) -> str | None:
        if value is None:
            return None
        value = value.strip()
        if not value:
            raise ValueError("知识标题和正文不能为空")
        return value

    @field_validator("summary", "source_ref")
    @classmethod
    def trim_optional_update_text(cls, value: str | None) -> str | None:
        return value.strip() if value and value.strip() else None

    @field_validator("tags")
    @classmethod
    def normalize_update_tags(cls, values: list[str] | None) -> list[str] | None:
        if values is None:
            return None
        return list(dict.fromkeys(value.strip() for value in values if value and value.strip()))[:20]


class KnowledgeSearchItem(BaseModel):
    key: str
    document_id: int | None = None
    source_type: KnowledgeSourceType
    title: str
    excerpt: str
    project_id: int | None = None
    project_name: str | None = None
    source_ref: str | None = None
    tags: list[str] = Field(default_factory=list)
    status: str
    match_terms: list[str] = Field(default_factory=list)
    match_score: int = 0
    target_path: str | None = None
    is_global: bool = False
    is_editable: bool = False
    updated_at: datetime


class KnowledgeDetailOut(KnowledgeSearchItem):
    summary: str | None = None
    content: str
    version: int
    author_id: int | None = None
    created_at: datetime


class KnowledgeListOut(BaseModel):
    items: list[KnowledgeSearchItem] = Field(default_factory=list)
    total: int
    page: int
    page_size: int
    source_counts: dict[str, int] = Field(default_factory=dict)
