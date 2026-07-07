"""P3.B 数据集 Pydantic schemas。"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field

DatasetFormat = Literal["csv", "json"]
DatasetSchemaFieldType = Literal["string", "number", "integer", "boolean", "object", "array"]
DatasetValidationPolicy = Literal["soft", "hard"]


class DatasetSchemaFieldIn(BaseModel):
    name: str = Field(..., min_length=1, max_length=128)
    type: DatasetSchemaFieldType = "string"
    required: bool = False
    default: Any = None


class TestDatasetCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=128)
    project_id: int
    description: str | None = None
    format: DatasetFormat = "json"
    rows: list[dict] = Field(default_factory=list)
    schema_fields: list[DatasetSchemaFieldIn] = Field(default_factory=list, max_length=100)
    validation_policy: DatasetValidationPolicy = "soft"


class TestDatasetUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=128)
    description: str | None = None
    rows: list[dict] | None = None
    schema_fields: list[DatasetSchemaFieldIn] | None = Field(default=None, max_length=100)
    validation_policy: DatasetValidationPolicy | None = None


class TestDatasetOut(BaseModel):
    id: int
    name: str
    description: str | None
    project_id: int
    format: DatasetFormat
    rows: list[dict]
    schema_fields: list[DatasetSchemaFieldIn] = Field(default_factory=list)
    validation_policy: DatasetValidationPolicy = "soft"
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
    schema_field_count: int = 0
    validation_policy: DatasetValidationPolicy = "soft"
    creator_id: int
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class TestDatasetVersionOut(BaseModel):
    id: int
    dataset_id: int
    version: int
    format: DatasetFormat
    row_count: int
    schema_field_count: int
    validation_policy: DatasetValidationPolicy = "soft"
    change_type: str
    created_by: int | None = None
    created_at: datetime

    model_config = {"from_attributes": True}


class DatasetImpactItemOut(BaseModel):
    id: int
    name: str
    reason: str


class DatasetImpactOut(BaseModel):
    dataset_id: int
    cases: list[DatasetImpactItemOut] = Field(default_factory=list)
    suites: list[DatasetImpactItemOut] = Field(default_factory=list)
    plans: list[DatasetImpactItemOut] = Field(default_factory=list)
    total_count: int = 0


class DatasetValidateIn(BaseModel):
    schema_fields: list[DatasetSchemaFieldIn] = Field(default_factory=list, max_length=100)
    rows: list[dict[str, Any]] = Field(default_factory=list)
    preview_limit: int = Field(default=5, ge=0, le=50)


class DatasetValidationIssueOut(BaseModel):
    row_index: int
    field: str
    message: str


class DatasetValidateOut(BaseModel):
    valid: bool
    row_count: int
    normalized_rows: list[dict[str, Any]]
    issues: list[DatasetValidationIssueOut] = Field(default_factory=list)
    validation_policy: DatasetValidationPolicy | None = None
    can_upload: bool | None = None
