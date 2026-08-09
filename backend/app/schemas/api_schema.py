from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field, field_validator


_MAX_SCHEMA_BYTES = 512 * 1024


def _validate_definition(value: dict) -> dict:
    if not isinstance(value, dict) or not value:
        raise ValueError("JSON Schema 必须是非空对象")
    import json

    if len(json.dumps(value, ensure_ascii=False, separators=(",", ":")).encode("utf-8")) > _MAX_SCHEMA_BYTES:
        raise ValueError("JSON Schema 超过 512KB 限制")
    return value


class ApiSchemaAssetCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=128)
    description: str | None = Field(default=None, max_length=2000)
    definition: dict

    _definition_validator = field_validator("definition")(_validate_definition)


class ApiSchemaAssetUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=128)
    description: str | None = Field(default=None, max_length=2000)
    definition: dict | None = None

    _definition_validator = field_validator("definition")(_validate_definition)


class ApiSchemaAssetOut(BaseModel):
    id: int
    project_id: int
    name: str
    description: str | None
    definition: dict
    version: int
    owner_id: int | None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}
