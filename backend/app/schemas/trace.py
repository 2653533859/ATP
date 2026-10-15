from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field

from app.schemas.case import TestRunOut
from app.schemas.plan import PlanRunOut
from app.schemas.suite import SuiteRunOut


class DistributedSpanOut(BaseModel):
    span_id: str
    parent_span_id: str | None = None
    service_name: str
    operation_name: str
    duration_ms: float
    start_time_offset_ms: float
    has_error: bool = False
    tags: dict[str, Any] = Field(default_factory=dict)
    children: list[DistributedSpanOut] = Field(default_factory=list)


class DistributedTraceWaterfallOut(BaseModel):
    trace_id: str
    root_service: str
    total_duration_ms: float
    span_count: int
    service_count: int
    services: list[str] = Field(default_factory=list)
    has_errors: bool = False
    spans: list[DistributedSpanOut] = Field(default_factory=list)


class TraceDetailOut(BaseModel):
    trace_id: str
    total_runs: int
    created_at: datetime | None = None
    last_seen_at: datetime | None = None
    case_runs: list[TestRunOut] = Field(default_factory=list)
    suite_runs: list[SuiteRunOut] = Field(default_factory=list)
    plan_runs: list[PlanRunOut] = Field(default_factory=list)
    distributed_trace: DistributedTraceWaterfallOut | None = None
