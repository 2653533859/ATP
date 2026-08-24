"""Contracts for project requirements and requirement-to-case traceability."""

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field, field_validator


RequirementStatus = Literal["draft", "active", "archived"]
RequirementPriority = Literal["P0", "P1", "P2", "P3"]
RequirementRelation = Literal["covers", "validates"]
CriterionStatus = Literal["draft", "approved"]


class AcceptanceCriterion(BaseModel):
    id: str | None = Field(default=None, max_length=32)
    text: str = Field(min_length=1, max_length=1_000)
    priority: RequirementPriority = "P2"
    status: CriterionStatus = "draft"

    @field_validator("text")
    @classmethod
    def trim_text(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("验收标准不能为空")
        return value


class RequirementCreate(BaseModel):
    project_id: int = Field(ge=1)
    title: str = Field(min_length=1, max_length=256)
    description: str | None = Field(default=None, max_length=20_000)
    status: RequirementStatus = "draft"
    priority: RequirementPriority = "P2"
    acceptance_criteria: list[AcceptanceCriterion] = Field(default_factory=list, max_length=50)
    source: str = Field(default="manual", min_length=1, max_length=32)
    source_ref: str | None = Field(default=None, max_length=512)
    owner_id: int | None = Field(default=None, ge=1)

    @field_validator("title")
    @classmethod
    def trim_title(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("需求标题不能为空")
        return value


class RequirementUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=256)
    description: str | None = Field(default=None, max_length=20_000)
    status: RequirementStatus | None = None
    priority: RequirementPriority | None = None
    acceptance_criteria: list[AcceptanceCriterion] | None = Field(default=None, max_length=50)
    source: str | None = Field(default=None, min_length=1, max_length=32)
    source_ref: str | None = Field(default=None, max_length=512)
    owner_id: int | None = Field(default=None, ge=1)

    @field_validator("title")
    @classmethod
    def trim_optional_title(cls, value: str | None) -> str | None:
        if value is None:
            return None
        value = value.strip()
        if not value:
            raise ValueError("需求标题不能为空")
        return value


class RequirementParseIn(BaseModel):
    project_id: int = Field(ge=1)
    text: str = Field(min_length=1, max_length=20_000)


class RequirementParseOut(BaseModel):
    title: str
    description: str
    acceptance_criteria: list[AcceptanceCriterion] = Field(default_factory=list)
    keywords: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)


class RequirementCaseLinkCreate(BaseModel):
    case_id: int = Field(ge=1)
    relation_type: RequirementRelation = "covers"
    criterion_ids: list[str] = Field(default_factory=list, max_length=50)
    note: str | None = Field(default=None, max_length=2_000)

    @field_validator("criterion_ids")
    @classmethod
    def normalize_criterion_ids(cls, values: list[str]) -> list[str]:
        return list(dict.fromkeys(value.strip() for value in values if value and value.strip()))


class RequirementCaseLinkOut(BaseModel):
    id: int
    requirement_id: int
    case_id: int
    case_name: str
    case_code: str
    case_type: str
    case_status: str
    review_status: str
    module_id: int
    module_name: str
    relation_type: RequirementRelation
    criterion_ids: list[str] = Field(default_factory=list)
    note: str | None = None
    created_by: int | None = None
    created_at: datetime


class RequirementListItem(BaseModel):
    id: int
    project_id: int
    requirement_code: str | None = None
    title: str
    description: str | None = None
    status: RequirementStatus
    priority: RequirementPriority
    acceptance_criteria: list[AcceptanceCriterion] = Field(default_factory=list)
    source: str
    source_ref: str | None = None
    version: int
    creator_id: int
    owner_id: int | None = None
    linked_case_count: int = 0
    covered_criterion_count: int = 0
    coverage_rate: float = 0.0
    created_at: datetime
    updated_at: datetime


class RequirementListOut(BaseModel):
    items: list[RequirementListItem] = Field(default_factory=list)
    total: int
    page: int
    page_size: int


class RequirementDetailOut(RequirementListItem):
    links: list[RequirementCaseLinkOut] = Field(default_factory=list)


class RequirementImpactCandidate(BaseModel):
    case_id: int
    case_name: str
    case_code: str
    case_type: str
    module_id: int
    module_name: str
    match_terms: list[str] = Field(default_factory=list)


class RequirementImpactOut(BaseModel):
    requirement_id: int
    requirement_version: int
    criteria_total: int
    criteria_covered: int
    coverage_rate: float
    linked_case_count: int
    impact_level: Literal["high", "medium", "low"]
    uncovered_criteria: list[AcceptanceCriterion] = Field(default_factory=list)
    candidate_cases: list[RequirementImpactCandidate] = Field(default_factory=list)
