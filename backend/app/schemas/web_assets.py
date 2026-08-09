from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field


class WebElementAssetCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=128)
    page_url: str | None = Field(default=None, max_length=512)
    locator: dict = Field(default_factory=dict)
    fallback_locators: list[dict] = Field(default_factory=list, max_length=8)
    description: str | None = None


class WebElementAssetUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=128)
    page_url: str | None = Field(default=None, max_length=512)
    locator: dict | None = None
    fallback_locators: list[dict] | None = Field(default=None, max_length=8)
    description: str | None = None


class WebElementAssetOut(BaseModel):
    id: int
    project_id: int
    name: str
    page_url: str | None
    locator: dict
    fallback_locators: list
    description: str | None
    version: int
    owner_id: int | None
    last_failed_at: datetime | None
    last_failure_reason: str | None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class WebElementFailureIn(BaseModel):
    reason: str = Field(..., min_length=1, max_length=2000)


class WebLocatorRepairIn(BaseModel):
    observed_locators: list[dict] = Field(default_factory=list, max_length=8)


class WebLocatorRepairCandidate(BaseModel):
    locator: dict
    confidence: float
    reason: str


class WebLocatorRepairOut(BaseModel):
    element_id: int
    candidates: list[WebLocatorRepairCandidate] = Field(default_factory=list)


class WebPageObjectCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=128)
    url_pattern: str | None = Field(default=None, max_length=512)
    description: str | None = None
    element_refs: list[dict] = Field(default_factory=list, max_length=100)
    actions: list[dict] = Field(default_factory=list, max_length=100)


class WebPageObjectUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=128)
    url_pattern: str | None = Field(default=None, max_length=512)
    description: str | None = None
    element_refs: list[dict] | None = Field(default=None, max_length=100)
    actions: list[dict] | None = Field(default=None, max_length=100)


class WebPageObjectOut(BaseModel):
    id: int
    project_id: int
    name: str
    url_pattern: str | None
    description: str | None
    element_refs: list
    actions: list
    version: int
    owner_id: int | None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}
