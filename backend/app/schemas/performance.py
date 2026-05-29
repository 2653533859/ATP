"""Schemas for HTTP performance testing."""
from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field

PerformanceExecutor = Literal["k6"]
PerformanceRunStatus = Literal["pending", "running", "success", "failed", "cancelled"]


class PerformanceTestCreate(BaseModel):
    project_id: int
    name: str = Field(..., min_length=1, max_length=128)
    description: str | None = None
    executor: PerformanceExecutor = "k6"
    script_object_name: str = Field(..., min_length=1, max_length=512)
    default_options: dict = Field(default_factory=dict)


class PerformanceTestUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=128)
    description: str | None = None
    script_object_name: str | None = Field(default=None, min_length=1, max_length=512)
    default_options: dict | None = None


class PerformanceTestOut(BaseModel):
    id: int
    project_id: int
    name: str
    description: str | None
    executor: str
    script_object_name: str
    default_options: dict
    creator_id: int | None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class PerformanceScriptUploadOut(BaseModel):
    script_object_name: str
    filename: str
    size: int


class PerformanceRunRawResultOut(BaseModel):
    url: str
    filename: str
    object_name: str


class PerformanceRunTrigger(BaseModel):
    environment_id: int | None = None
    options: dict = Field(default_factory=dict)


class PerformanceRunOut(BaseModel):
    id: int
    performance_test_id: int
    project_id: int
    environment_id: int | None
    status: PerformanceRunStatus | str
    triggered_by: int | None
    started_at: datetime | None
    finished_at: datetime | None
    duration_ms: int | None
    options_snapshot: dict
    summary: dict
    raw_result_object_name: str | None
    error_message: str | None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}
