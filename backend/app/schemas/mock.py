from datetime import datetime

from pydantic import BaseModel, Field, field_validator

from app.models.mock import MockMethod


def _normalize_path(path: str | None) -> str | None:
    if path is None:
        return None
    normalized = path.strip()
    if not normalized:
        return '/'
    return '/' + normalized.lstrip('/')


class MockRuleCreate(BaseModel):
    name: str
    project_id: int
    method: MockMethod
    path: str
    status_code: int = 200
    response_headers: dict = Field(default_factory=dict)
    response_body: str | None = None
    delay_ms: int = 0
    is_enabled: bool = True

    @field_validator('path')
    @classmethod
    def normalize_path(cls, value: str) -> str:
        return _normalize_path(value) or '/'


class MockRuleUpdate(BaseModel):
    name: str | None = None
    method: MockMethod | None = None
    path: str | None = None
    status_code: int | None = None
    response_headers: dict | None = None
    response_body: str | None = None
    delay_ms: int | None = None
    is_enabled: bool | None = None

    @field_validator('path')
    @classmethod
    def normalize_path(cls, value: str | None) -> str | None:
        return _normalize_path(value)


class MockRuleOut(BaseModel):
    id: int
    name: str
    project_id: int
    method: MockMethod
    path: str
    status_code: int
    response_headers: dict
    response_body: str | None
    delay_ms: int
    is_enabled: bool
    creator_id: int
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}
