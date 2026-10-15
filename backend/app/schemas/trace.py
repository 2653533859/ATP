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


class TraceAnomalyItemOut(BaseModel):
    span_id: str
    service_name: str
    operation_name: str
    category: str
    severity: str
    duration_ms: float
    description: str
    statement: str | None = None
    http_status: int | None = None


class TraceAnomalyClusterOut(BaseModel):
    trace_id: str
    root_cause_service: str
    root_cause_span: str | None = None
    root_cause_category: str
    root_cause_summary: str
    error_span_count: int
    slow_span_count: int
    total_anomalies: int
    anomalies: list[TraceAnomalyItemOut] = Field(default_factory=list)


class DistributedTraceWaterfallOut(BaseModel):
    trace_id: str
    root_service: str
    total_duration_ms: float
    span_count: int
    service_count: int
    services: list[str] = Field(default_factory=list)
    has_errors: bool = False
    spans: list[DistributedSpanOut] = Field(default_factory=list)
    anomaly_cluster: TraceAnomalyClusterOut | None = None


class TraceDetailOut(BaseModel):
    trace_id: str
    total_runs: int
    created_at: datetime | None = None
    last_seen_at: datetime | None = None
    case_runs: list[TestRunOut] = Field(default_factory=list)
    suite_runs: list[SuiteRunOut] = Field(default_factory=list)
    plan_runs: list[PlanRunOut] = Field(default_factory=list)
    distributed_trace: DistributedTraceWaterfallOut | None = None
