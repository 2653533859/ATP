"""P3.B 数据集 Pydantic schemas。"""
from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field

DatasetFormat = Literal["csv", "json"]


class TestDatasetCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=128)
    project_id: int
    description: str | None = None
    format: DatasetFormat = "json"
    rows: list[dict] = Field(default_factory=list)


class TestDatasetUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=128)
    description: str | None = None
    rows: list[dict] | None = None


class TestDatasetOut(BaseModel):
    id: int
    name: str
    description: str | None
    project_id: int
    format: DatasetFormat
    rows: list[dict]
    creator_id: int
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class TestDatasetListItem(BaseModel):
    id: int
    name: str
    description: str | None
    project_id: int
    format: DatasetFormat
    row_count: int
    creator_id: int
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}
