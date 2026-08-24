"""Contracts for the administrator remote toolbox diagnostics."""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field


RemoteToolboxStatus = Literal["ok", "degraded", "error"]
ToolboxCheckStatus = Literal["ok", "warning", "error"]
ToolboxCheckCategory = Literal["infrastructure", "execution"]


class RemoteToolboxResource(BaseModel):
    id: str
    name: str
    status: ToolboxCheckStatus
    summary: str
    metadata: dict[str, object] = Field(default_factory=dict)


class RemoteToolboxCheck(BaseModel):
    key: str
    category: ToolboxCheckCategory
    status: ToolboxCheckStatus
    code: str
    latency_ms: float
    resources: list[RemoteToolboxResource] = Field(default_factory=list)


class RemoteToolboxOverview(BaseModel):
    status: RemoteToolboxStatus
    checked_at: datetime
    checks: list[RemoteToolboxCheck]
