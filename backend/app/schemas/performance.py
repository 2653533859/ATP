"""Schemas for HTTP performance testing."""

from __future__ import annotations

from datetime import datetime
from datetime import timezone
import re
from typing import Literal

from pydantic import BaseModel, Field, computed_field, field_serializer

from app.services.performance_options import ENVIRONMENT_SNAPSHOT_KEY

PerformanceExecutor = Literal["k6", "locust", "grpc"]
PerformanceRunStatus = Literal["pending", "running", "cancelling", "success", "failed", "cancelled"]
PerformanceGateStatus = Literal["pending", "passed", "failed", "not_configured", "cancelled"]
_SENSITIVE_ENV_KEY_RE = re.compile(
    r"(?:token|secret|password|passwd|api[_-]?key|credential|authorization|cookie)",
    re.IGNORECASE,
)


class PerformanceTestCreate(BaseModel):
    project_id: int
    name: str = Field(..., min_length=1, max_length=128)
    description: str | None = None
    executor: PerformanceExecutor = "k6"
    script_object_name: str = Field(..., min_length=1, max_length=512)
    default_options: dict = Field(default_factory=dict)
    dataset_id: int | None = Field(default=None, ge=1)


class PerformanceTestUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=128)
    description: str | None = None
    script_object_name: str | None = Field(default=None, min_length=1, max_length=512)
    default_options: dict | None = None
    executor: PerformanceExecutor | None = None
    dataset_id: int | None = Field(default=None, ge=1)


class PerformanceExecutorOut(BaseModel):
    name: str
    label: str
    ready: bool
    script_extensions: list[str]
    supports_visual: bool
    supports_dataset: bool
    supports_http: bool
    supports_grpc: bool
    description: str


class PerformanceTestOut(BaseModel):
    id: int
    project_id: int
    name: str
    description: str | None
    executor: str
    script_object_name: str
    default_options: dict
    creator_id: int | None
    baseline_run_id: int | None
    schedule_enabled: bool
    cron_expression: str | None
    schedule_timezone: str
    schedule_environment_id: int | None
    schedule_node_id: int | None
    dataset_id: int | None
    schedule_options: dict
    last_scheduled_run_at: datetime | None
    next_run_at: datetime | None
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
    performance_node_id: int | None = Field(default=None, ge=1)
    options: dict = Field(default_factory=dict)


class PerformanceScheduleUpdate(BaseModel):
    enabled: bool = False
    cron_expression: str | None = Field(default=None, max_length=128)
    timezone: str = Field(default="Asia/Shanghai", min_length=1, max_length=64)
    environment_id: int | None = None
    performance_node_id: int | None = Field(default=None, ge=1)
    options: dict = Field(default_factory=dict)


class PerformanceBaselineUpdate(BaseModel):
    run_id: int = Field(..., ge=1)


class PerformanceGateOut(BaseModel):
    status: PerformanceGateStatus
    ready: bool
    run_status: PerformanceRunStatus | str
    total: int
    passed: int
    failed: int


class PerformanceBaselineMetricOut(BaseModel):
    metric: str
    preferred_direction: Literal["higher", "lower"]
    baseline: float | None
    current: float | None
    delta: float | None
    delta_percent: float | None
    direction: Literal["improvement", "regression", "unchanged", "unknown"]


class PerformanceBaselineComparisonOut(BaseModel):
    baseline_run_id: int
    run_id: int
    metrics: list[PerformanceBaselineMetricOut]


class PerformanceMetricSampleOut(BaseModel):
    id: int
    run_id: int
    captured_at: datetime
    node_id: str
    source: str
    metrics: dict[str, float]
    errors: list[str]

    model_config = {"from_attributes": True}


class PerformanceRunOut(BaseModel):
    id: int
    performance_test_id: int
    project_id: int
    environment_id: int | None
    performance_node_id: int | None
    dataset_id: int | None
    dataset_version: int | None
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

    @field_serializer("options_snapshot")
    def serialize_options_snapshot(self, value: dict) -> dict:
        """Never return the worker-only encrypted environment snapshot to clients."""
        result = {key: item for key, item in value.items() if key != ENVIRONMENT_SNAPSHOT_KEY}
        env = result.get("env")
        if isinstance(env, dict):
            result["env"] = {key: item for key, item in env.items() if not _SENSITIVE_ENV_KEY_RE.search(str(key))}
        return result

    @computed_field  # type: ignore[prop-decorator]
    @property
    def progress_percent(self) -> int:
        """Expose a useful live estimate without persisting transient progress."""
        if self.status in {"success", "failed", "cancelled"}:
            return 100
        if self.status == "pending":
            return 0
        if self.status == "cancelling":
            return 99
        if self.started_at is None:
            return 1

        started_at = self.started_at
        if started_at.tzinfo is None:
            started_at = started_at.replace(tzinfo=timezone.utc)
        elapsed_seconds = max(0.0, (datetime.now(timezone.utc) - started_at).total_seconds())
        expected_seconds = _expected_duration_seconds(self.options_snapshot)
        if expected_seconds <= 0:
            return 10
        return max(1, min(95, round(elapsed_seconds / expected_seconds * 100)))


def _expected_duration_seconds(options: dict) -> float:
    duration = options.get("duration") if isinstance(options, dict) else None
    parsed_duration = _parse_duration_seconds(duration)
    if isinstance(options, dict):
        for key in ("run_time", "duration_seconds"):
            alternate_duration = _parse_duration_seconds(options.get(key))
            if alternate_duration is not None:
                parsed_duration = max(parsed_duration or 0, alternate_duration)
    stages = options.get("stages") if isinstance(options, dict) else None
    if isinstance(stages, list):
        stage_seconds = sum(
            parsed
            for stage in stages
            if isinstance(stage, dict)
            for parsed in [_parse_duration_seconds(stage.get("duration"))]
            if parsed is not None
        )
        parsed_duration = max(parsed_duration or 0, stage_seconds)
    return parsed_duration or 0


def _parse_duration_seconds(value: object) -> float | None:
    if isinstance(value, (int, float)) and value >= 0:
        return float(value)
    if not isinstance(value, str):
        return None
    match = re.fullmatch(r"\s*(\d+(?:\.\d+)?)\s*(ms|s|m|h)?\s*", value, re.IGNORECASE)
    if not match:
        return None
    amount = float(match.group(1))
    multiplier = {"ms": 0.001, "s": 1, "m": 60, "h": 3600}.get((match.group(2) or "s").lower(), 1)
    return amount * multiplier
