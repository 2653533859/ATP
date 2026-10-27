"""Schemas for Windows Desktop to Cloud result synchronization (D2 Contract)."""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


class CloudSyncStatus(str, Enum):
    pending = "pending"
    syncing = "syncing"
    synced = "synced"
    failed = "failed"


class CloudStepSummary(BaseModel):
    """Sanitized step-level execution summary without payloads or binary assets."""

    step_index: int = Field(..., ge=0)
    name: str = Field(..., max_length=256)
    status: str = Field(..., max_length=32)
    duration_ms: int | None = Field(default=None, ge=0)
    error_summary: str | None = Field(default=None, max_length=1024)


class CloudRunSummary(BaseModel):
    """Versioned result summary contract (Format Version 1).

    Guarantees:
    - Never contains raw request/response bodies or query parameters.
    - Never contains tokens, cookies, auth headers, or credentials.
    - Never contains raw screenshots, recordings, or local file attachments.
    - Uniquely identified by (client_id, run_type, run_id).
    """

    schema_version: int = Field(default=1, ge=1)
    client_id: str = Field(..., min_length=1, max_length=64)
    machine_name: str = Field(..., max_length=64)
    unique_key: str = Field(..., min_length=1, max_length=128)
    run_type: str = Field(..., max_length=32)  # case | suite | plan | mobile_special | performance
    run_id: int = Field(..., ge=1)
    project_name: str = Field(..., max_length=128)
    project_code: str = Field(..., max_length=64)
    title: str = Field(..., max_length=256)
    status: str = Field(..., max_length=32)
    started_at: datetime | None = None
    finished_at: datetime | None = None
    duration_ms: int | None = Field(default=None, ge=0)
    triggered_by: str = Field(default="admin", max_length=64)
    environment: str | None = Field(default=None, max_length=64)
    metrics: dict[str, Any] = Field(default_factory=dict)
    error_summary: str | None = Field(default=None, max_length=2048)
    steps: list[CloudStepSummary] = Field(default_factory=list)


class OutboxRecord(BaseModel):
    """Local outbox persistence record."""

    id: int
    client_id: str
    run_type: str
    run_id: int
    unique_key: str
    payload: CloudRunSummary
    status: CloudSyncStatus
    attempts: int
    last_error: str | None
    created_at: datetime
    updated_at: datetime
    synced_at: datetime | None = None
