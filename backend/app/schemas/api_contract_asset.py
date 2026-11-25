"""Schemas for reusable Provider/Consumer API contracts."""

from __future__ import annotations

from datetime import datetime
import json
from typing import Literal

from pydantic import BaseModel, Field, field_validator, model_validator


ContractRole = Literal["provider", "consumer"]
ContractFormat = Literal["openapi", "swagger", "json_schema"]


def _validate_definition(value: dict | None) -> dict | None:
    if value is None:
        return None
    if not value:
        raise ValueError("契约定义不能为空")
    if len(json.dumps(value, ensure_ascii=False)) > 2 * 1024 * 1024:
        raise ValueError("契约定义不能超过 2 MB")
    return value


class ApiContractAssetCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=128)
    role: ContractRole
    format: ContractFormat
    description: str | None = Field(default=None, max_length=2000)
    definition: dict

    _definition_validator = field_validator("definition")(_validate_definition)


class ApiContractAssetUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=128)
    role: ContractRole | None = None
    format: ContractFormat | None = None
    description: str | None = Field(default=None, max_length=2000)
    definition: dict | None = None

    _definition_validator = field_validator("definition")(_validate_definition)

    @model_validator(mode="after")
    def reject_explicit_null_required_fields(self) -> "ApiContractAssetUpdate":
        for required_field in ("name", "role", "format", "definition"):
            if required_field in self.model_fields_set and getattr(self, required_field) is None:
                raise ValueError(f"字段 {required_field} 不能设为 null")
        return self


class ApiContractAssetOut(BaseModel):
    id: int
    project_id: int
    name: str
    role: ContractRole
    format: ContractFormat
    description: str | None
    definition: dict
    version: int
    owner_id: int | None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class ApiContractAssetCompareIn(BaseModel):
    baseline_asset_id: int = Field(gt=0)
    current_asset_id: int = Field(gt=0)
