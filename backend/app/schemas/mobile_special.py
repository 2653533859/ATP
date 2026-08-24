"""Pydantic schemas for mobile special testing domain."""

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field

from app.models.mobile_special import (
    TaskType,
    SourceType,
    DeviceScopeType,
    RunStatus,
    TriggerType,
    IncidentType,
    MetricType,
    ArtifactType,
)


# ---- Task Schemas ----


class MobileSpecialTaskCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=256)
    project_id: int
    task_type: TaskType
    source_type: SourceType = SourceType.apk_only
    source_id: Optional[int] = None
    device_scope_type: DeviceScopeType
    device_id: Optional[int] = None
    device_group_tag: Optional[str] = Field(None, max_length=128)
    apk_id: Optional[int] = None
    app_package: Optional[str] = Field(None, max_length=256)
    config_json: dict = Field(default_factory=dict)
    schedule_enabled: bool = False
    cron_expression: Optional[str] = Field(None, max_length=64)
    created_by: Optional[int] = None


class MobileSpecialTaskUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=256)
    task_type: Optional[TaskType] = None
    source_type: Optional[SourceType] = None
    source_id: Optional[int] = None
    device_scope_type: Optional[DeviceScopeType] = None
    device_id: Optional[int] = None
    device_group_tag: Optional[str] = Field(None, max_length=128)
    apk_id: Optional[int] = None
    app_package: Optional[str] = Field(None, max_length=256)
    config_json: Optional[dict] = None
    schedule_enabled: Optional[bool] = None
    cron_expression: Optional[str] = Field(None, max_length=64)
    updated_by: Optional[int] = None


class MobileSpecialTaskOut(BaseModel):
    id: int
    name: str
    project_id: int
    task_type: TaskType
    source_type: SourceType
    source_id: Optional[int] = None
    device_scope_type: DeviceScopeType
    device_id: Optional[int] = None
    device_group_tag: Optional[str] = None
    apk_id: Optional[int] = None
    app_package: Optional[str] = None
    config_json: dict
    schedule_enabled: bool
    cron_expression: Optional[str] = None
    last_run_at: Optional[datetime] = None
    next_run_at: Optional[datetime] = None
    created_by: Optional[int] = None
    updated_by: Optional[int] = None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


# ---- Run Schemas ----


class MobileSpecialRunOut(BaseModel):
    id: int
    task_id: int
    task_type: TaskType
    status: RunStatus
    device_id: Optional[int] = None
    device_serial: Optional[str] = None
    apk_id: Optional[int] = None
    app_package: Optional[str] = None
    started_at: Optional[datetime] = None
    finished_at: Optional[datetime] = None
    duration_ms: Optional[int] = None
    summary_json: dict
    config_snapshot: dict
    trigger_type: TriggerType
    triggered_by: Optional[int] = None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class MobileSpecialRunListItem(MobileSpecialRunOut):
    """Extended run item for list views with task_name joined."""

    task_name: Optional[str] = None


class RunSummary(BaseModel):
    """Summary fields for a completed run. Fields vary by task_type."""

    # Performance metrics
    avg_cpu_pct: Optional[float] = None
    peak_cpu_pct: Optional[float] = None
    avg_mem_mb: Optional[float] = None
    peak_mem_mb: Optional[float] = None
    avg_battery_pct: Optional[float] = None
    # Stability metrics
    explore_duration_seconds: Optional[int] = None
    operation_interval_ms: Optional[int] = None
    crash_count: int = 0
    anr_count: int = 0
    completed_action_count: int = 0
    app_restart_count: int = 0
    # Fluency metrics
    avg_fps: Optional[float] = None
    total_jank_count: int = 0
    # General
    error_message: Optional[str] = None


class RunTriggerRequest(BaseModel):
    device_id: Optional[int] = None
    apk_id: Optional[int] = None
    app_package: Optional[str] = None


# ---- Metric Sample Schemas ----


class MobileMetricSampleOut(BaseModel):
    id: int
    run_id: int
    sample_time: datetime
    metric_type: MetricType
    metric_value: float
    source: Optional[str] = None
    extra_json: dict

    model_config = {"from_attributes": True}


# ---- Incident Schemas ----


class MobileIncidentOut(BaseModel):
    id: int
    run_id: int
    incident_type: IncidentType
    event_time: datetime
    title: Optional[str] = None
    detail: Optional[str] = None
    process_name: Optional[str] = None
    thread_name: Optional[str] = None
    artifact_path: Optional[str] = None

    model_config = {"from_attributes": True}


# ---- Artifact Schemas ----


class MobileRunArtifactOut(BaseModel):
    id: int
    run_id: int
    artifact_type: ArtifactType
    file_path: str
    file_name: str
    file_size: Optional[int] = None
    created_at: datetime

    model_config = {"from_attributes": True}


class MobileRunEventOut(BaseModel):
    id: int
    run_id: int
    sequence: int
    event_time: datetime
    event_type: str
    phase: Optional[str] = None
    action: Optional[str] = None
    level: Optional[str] = None
    message: Optional[str] = None
    parameters_json: dict
    result_json: dict
    duration_ms: Optional[int] = None

    model_config = {"from_attributes": True}


# ---- Statistics Schemas ----


class MobileSpecialOverviewItem(BaseModel):
    total_runs: int
    completed_runs: int
    failed_runs: int
    running_runs: int
    pass_rate: float
    avg_duration_ms: Optional[float] = None
    total_incidents: int
    recent_runs_7d: int


class MobileSpecialTrendItem(BaseModel):
    date: str
    total: int
    completed: int
    failed: int
    pass_rate: float


class MobileSpecialTaskStatItem(BaseModel):
    task_id: int
    task_name: str
    task_type: TaskType
    total_runs: int
    completed_runs: int
    failed_runs: int
    pass_rate: float
    avg_duration_ms: Optional[float] = None
    last_run_at: Optional[datetime] = None
