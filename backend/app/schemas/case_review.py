"""Contracts for the project-aware case review workbench."""

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field


ReviewQueueStatus = Literal["all", "pending", "approved", "rejected"]
ReviewAction = Literal["approve", "reject"]


class CaseReviewQueueItem(BaseModel):
    id: int
    project_id: int
    project_name: str
    module_id: int
    module_name: str
    name: str
    case_code: str
    summary: str
    case_type: str
    priority: str
    case_level: str
    review_status: str
    automation_status: str
    creator_id: int
    owner_id: int | None = None
    submitted_at: datetime | None = None
    reviewed_at: datetime | None = None
    reviewed_by: int | None = None
    reviewer_name: str | None = None
    review_comment: str | None = None
    step_count: int = 0
    snapshot_count: int = 0
    latest_snapshot_version: int | None = None
    created_at: datetime
    updated_at: datetime


class CaseReviewCounts(BaseModel):
    all: int = 0
    pending: int = 0
    approved: int = 0
    rejected: int = 0


class CaseReviewQueueOut(BaseModel):
    items: list[CaseReviewQueueItem] = Field(default_factory=list)
    total: int
    page: int
    page_size: int
    counts: CaseReviewCounts


class CaseReviewBatchIn(BaseModel):
    case_ids: list[int] = Field(min_length=1, max_length=100)
    action: ReviewAction
    comment: str | None = Field(default=None, max_length=2_000)


class CaseReviewBatchOut(BaseModel):
    requested: int
    processed: int
    processed_ids: list[int] = Field(default_factory=list)
    skipped_ids: list[int] = Field(default_factory=list)


class CaseReviewHistoryItem(BaseModel):
    id: int
    case_id: int
    action: str
    status: str
    comment: str | None = None
    reviewer_id: int | None = None
    reviewer_name: str = ""
    source: str = "case"
    snapshot_version: int | None = None
    created_at: datetime
