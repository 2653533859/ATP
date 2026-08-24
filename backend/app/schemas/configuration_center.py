"""Read-only configuration center contracts."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field


ConfigurationSnapshotDomain = Literal[
    "environment",
    "global_variable",
    "ai_llm",
    "storage_policy",
    "notification",
    "performance_node",
]
ConfigurationDiffChangeType = Literal["added", "removed", "changed"]
ConfigurationCurrentStatus = Literal["available", "missing"]
ConfigurationImpactSeverity = Literal["high", "medium", "low"]


class ConfigurationEntryOut(BaseModel):
    """A safe summary of one configuration resource."""

    domain: str
    resource_id: int | None = None
    project_id: int | None = None
    name: str
    status: str
    updated_at: datetime | None = None
    summary: dict[str, Any] = Field(default_factory=dict)
    route: str
    can_manage: bool = False


class ConfigurationSectionOut(BaseModel):
    """One configuration domain and the resources visible in it."""

    key: str
    title: str
    description: str
    route: str
    project_scoped: bool = False
    readonly: bool = False
    available: bool = True
    count: int = 0
    entries: list[ConfigurationEntryOut] = Field(default_factory=list)


class ConfigurationCenterOverviewOut(BaseModel):
    checked_at: datetime
    project_id: int | None = None
    sections: list[ConfigurationSectionOut] = Field(default_factory=list)


class ConfigurationRevisionCreateIn(BaseModel):
    domain: ConfigurationSnapshotDomain
    resource_id: int = Field(gt=0)
    reason: str | None = Field(default=None, max_length=512)


class ConfigurationRevisionRollbackIn(BaseModel):
    """Explicit confirmation required before a historical version is restored."""

    confirmation: Literal["ROLLBACK"] = Field(description="必须明确填写 ROLLBACK，避免误触发配置回滚")


class ConfigurationRevisionOut(BaseModel):
    id: int
    domain: str
    resource_id: int
    project_id: int | None = None
    resource_name: str
    fingerprint: str
    reason: str | None = None
    redacted_payload: dict[str, Any] = Field(default_factory=dict)
    created_by: int | None = None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class ConfigurationRevisionRollbackOut(BaseModel):
    source_revision_id: int
    resource_id: int
    domain: str
    changed: bool
    message: str
    revision: ConfigurationRevisionOut


class ConfigurationRevisionDiffChangeOut(BaseModel):
    """One changed field; sensitive fields deliberately omit both values."""

    path: str
    change_type: ConfigurationDiffChangeType
    changed: bool = True
    sensitive: bool = False
    before: Any = None
    after: Any = None


class ConfigurationImpactOut(BaseModel):
    code: str
    title: str
    description: str
    severity: ConfigurationImpactSeverity
    affected_features: list[str] = Field(default_factory=list)


class ConfigurationRevisionDiffOut(BaseModel):
    revision_id: int
    domain: str
    resource_id: int
    project_id: int | None = None
    resource_name: str
    historical_fingerprint: str
    current_fingerprint: str | None = None
    current_available: bool
    current_status: ConfigurationCurrentStatus
    changed: bool
    changed_field_count: int = Field(ge=0)
    sensitive_changed_field_count: int = Field(ge=0)
    truncated: bool = False
    message: str | None = None
    changes: list[ConfigurationRevisionDiffChangeOut] = Field(default_factory=list)
    impacts: list[ConfigurationImpactOut] = Field(default_factory=list)
