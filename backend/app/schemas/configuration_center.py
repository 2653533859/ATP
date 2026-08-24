"""Read-only configuration center contracts."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


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
