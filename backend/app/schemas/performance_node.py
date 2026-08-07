"""Schemas for performance load-injector nodes."""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field


PerformanceNodeStatus = Literal["online", "offline", "disabled", "draining"]


class PerformanceNodeCreate(BaseModel):
    node_id: str = Field(..., min_length=1, max_length=128, pattern=r"^[A-Za-z0-9._:-]+$")
    name: str = Field(..., min_length=1, max_length=128)
    queue_name: str = Field(default="performance", min_length=1, max_length=128, pattern=r"^[A-Za-z0-9._:-]+$")
    enabled: bool = True
    labels: dict = Field(default_factory=dict)
    capabilities: dict = Field(default_factory=dict)
    max_vus: int | None = Field(default=None, ge=1)
    max_concurrency: int | None = Field(default=None, ge=1)
    egress_allowlist: list[str] = Field(default_factory=list)


class PerformanceNodeUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=128)
    queue_name: str | None = Field(default=None, min_length=1, max_length=128, pattern=r"^[A-Za-z0-9._:-]+$")
    enabled: bool | None = None
    status: Literal["online", "offline", "draining"] | None = None
    labels: dict | None = None
    capabilities: dict | None = None
    max_vus: int | None = Field(default=None, ge=1)
    max_concurrency: int | None = Field(default=None, ge=1)
    egress_allowlist: list[str] | None = None


class PerformanceNodeOut(BaseModel):
    id: int
    node_id: str
    name: str
    queue_name: str
    status: PerformanceNodeStatus | str
    enabled: bool
    labels: dict
    capabilities: dict
    max_vus: int | None
    max_concurrency: int | None
    egress_allowlist: list[str]
    last_heartbeat_at: datetime | None
    last_error: str | None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}
