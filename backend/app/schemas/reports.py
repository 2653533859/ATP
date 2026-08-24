"""Project-level test report contracts."""

from datetime import datetime

from pydantic import BaseModel, Field


class ReportTrendItem(BaseModel):
    date: str
    total: int
    passed: int
    failed: int
    error: int
    pass_rate: float
    avg_duration_ms: float | None = None


class ReportRunItem(BaseModel):
    id: int
    project_id: int
    case_id: int
    case_name: str
    case_type: str
    status: str
    duration_ms: int | None = None
    error_message: str | None = None
    created_at: datetime


class ReportOverviewOut(BaseModel):
    project_id: int | None = None
    days: int = Field(ge=1)
    total_cases: int
    executed_cases: int
    coverage_rate: float
    total_runs: int
    passed_runs: int
    failed_runs: int
    error_runs: int
    pass_rate: float
    avg_duration_ms: float | None = None
    open_defects: int
    defect_health_rate: float
    quality_score: float
    trend: list[ReportTrendItem] = Field(default_factory=list)
    recent_runs: list[ReportRunItem] = Field(default_factory=list)


class ReportRunSnapshot(BaseModel):
    id: int
    project_id: int
    case_id: int
    case_name: str
    case_type: str
    status: str
    duration_ms: int | None = None
    total_steps: int
    passed_steps: int
    failed_steps: int
    error_steps: int
    error_message: str | None = None
    created_at: datetime


class ReportCompareMetric(BaseModel):
    key: str
    label: str
    baseline: float
    current: float
    delta: float
    unit: str | None = None


class ReportCompareOut(BaseModel):
    project_id: int
    baseline: ReportRunSnapshot
    current: ReportRunSnapshot
    metrics: list[ReportCompareMetric] = Field(default_factory=list)
    has_regression: bool
