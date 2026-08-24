from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field, field_validator


DefectStatus = Literal["open", "in_progress", "resolved", "reopened", "closed"]
DefectPriority = Literal["P0", "P1", "P2", "P3"]
DefectSeverity = Literal["blocker", "critical", "major", "minor", "trivial"]
DefectRunType = Literal["case", "suite", "plan", "android", "performance"]


class DefectRunLinkCreate(BaseModel):
    run_type: DefectRunType
    run_id: int = Field(ge=1)
    case_id: int | None = Field(default=None, ge=1)


class DefectCreate(BaseModel):
    project_id: int = Field(ge=1)
    case_id: int | None = Field(default=None, ge=1)
    title: str = Field(min_length=1, max_length=256)
    description: str | None = Field(default=None, max_length=20_000)
    status: DefectStatus = "open"
    priority: DefectPriority = "P2"
    severity: DefectSeverity = "major"
    fingerprint: str | None = Field(default=None, min_length=1, max_length=128)
    labels: list[str] = Field(default_factory=list, max_length=20)
    assignee_id: int | None = Field(default=None, ge=1)
    run_links: list[DefectRunLinkCreate] = Field(default_factory=list, max_length=20)

    @field_validator("title")
    @classmethod
    def title_must_not_be_blank(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("缺陷标题不能为空")
        return value


class DefectUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=256)
    description: str | None = Field(default=None, max_length=20_000)
    status: DefectStatus | None = None
    priority: DefectPriority | None = None
    severity: DefectSeverity | None = None
    resolution: str | None = Field(default=None, max_length=64)
    labels: list[str] | None = Field(default=None, max_length=20)
    assignee_id: int | None = Field(default=None, ge=1)

    @field_validator("title")
    @classmethod
    def update_title_must_not_be_blank(cls, value: str | None) -> str | None:
        if value is None:
            return value
        value = value.strip()
        if not value:
            raise ValueError("缺陷标题不能为空")
        return value


class DefectRunLinkOut(BaseModel):
    id: int
    run_type: DefectRunType
    run_id: int
    case_id: int | None = None
    evidence: dict = Field(default_factory=dict)
    linked_by: int | None = None
    created_at: datetime

    model_config = {"from_attributes": True}


class DefectOut(BaseModel):
    id: int
    project_id: int
    case_id: int | None = None
    title: str
    description: str | None = None
    status: DefectStatus
    priority: DefectPriority
    severity: DefectSeverity
    fingerprint: str | None = None
    resolution: str | None = None
    labels: list[str] = Field(default_factory=list)
    occurrence_count: int
    last_seen_at: datetime | None = None
    creator_id: int | None = None
    assignee_id: int | None = None
    created_at: datetime
    updated_at: datetime
    run_links: list[DefectRunLinkOut] = Field(default_factory=list)

    model_config = {"from_attributes": True}


class DefectCreateFromRun(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=256)
    description: str | None = Field(default=None, max_length=20_000)
    priority: DefectPriority = "P2"
    severity: DefectSeverity = "major"
    assignee_id: int | None = Field(default=None, ge=1)


class DefectMutationOut(BaseModel):
    defect: DefectOut
    created: bool
    duplicate_of: int | None = None


class DefectListOut(BaseModel):
    items: list[DefectOut]
    total: int
    page: int
    page_size: int
