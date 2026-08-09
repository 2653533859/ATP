from datetime import datetime

from pydantic import BaseModel, Field


class WebVisualBaselineOut(BaseModel):
    id: int
    project_id: int
    name: str
    page_url: str | None
    object_name: str
    content_type: str
    width: int | None
    height: int | None
    threshold: float
    pixel_threshold: int
    ignore_regions: list[dict]
    version: int
    owner_id: int | None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class WebVisualBaselineSettings(BaseModel):
    threshold: float = Field(default=0.01, ge=0, le=1)
    pixel_threshold: int = Field(default=10, ge=0, le=255)
    ignore_regions: list[dict] = Field(default_factory=list, max_length=100)
