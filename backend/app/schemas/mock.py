from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field, field_validator

from app.models.mock import MockMethod


def _normalize_path(path: str | None) -> str | None:
    if path is None:
        return None
    normalized = path.strip()
    if not normalized:
        return "/"
    return "/" + normalized.lstrip("/")


class MockMatchConditions(BaseModel):
    query: dict[str, Any] = Field(default_factory=dict)
    headers: dict[str, Any] = Field(default_factory=dict)
    body: dict[str, Any] = Field(default_factory=dict)

    @field_validator("query", "headers", "body")
    @classmethod
    def validate_condition_values(cls, value: dict[str, Any]) -> dict[str, Any]:
        if len(value) > 50:
            raise ValueError("a condition group cannot contain more than 50 fields")

        for field_name, condition in value.items():
            if not field_name.strip():
                raise ValueError("condition field names cannot be empty")
            if isinstance(condition, dict):
                if len(condition) != 1:
                    raise ValueError("a condition operator object must contain exactly one operator")
                operator, operand = next(iter(condition.items()))
                if operator == "$exists":
                    if not isinstance(operand, bool):
                        raise ValueError("$exists expects a boolean")
                elif operator == "$contains":
                    if not isinstance(operand, str) or len(operand) > 512:
                        raise ValueError("$contains expects a string of at most 512 characters")
                elif operator == "$in":
                    if not isinstance(operand, list) or len(operand) > 20:
                        raise ValueError("$in expects a list with at most 20 scalar values")
                    if any(isinstance(item, (dict, list)) for item in operand):
                        raise ValueError("$in values must be scalar values")
                else:
                    raise ValueError("unsupported condition operator")
            elif not isinstance(condition, (str, int, float, bool)) and condition is not None:
                raise ValueError("condition values must be scalar values or supported operators")
        return value


class MockRuleCreate(BaseModel):
    name: str
    project_id: int
    method: MockMethod
    path: str
    status_code: int = 200
    response_headers: dict = Field(default_factory=dict)
    response_body: str | None = None
    match_conditions: MockMatchConditions = Field(default_factory=MockMatchConditions)
    delay_ms: int = 0
    is_enabled: bool = True
    render_template: bool = False
    record_requests: bool = False

    @field_validator("path")
    @classmethod
    def normalize_path(cls, value: str) -> str:
        return _normalize_path(value) or "/"


class MockRuleUpdate(BaseModel):
    name: str | None = None
    method: MockMethod | None = None
    path: str | None = None
    status_code: int | None = None
    response_headers: dict | None = None
    response_body: str | None = None
    match_conditions: MockMatchConditions | None = None
    delay_ms: int | None = None
    is_enabled: bool | None = None
    render_template: bool | None = None
    record_requests: bool | None = None

    @field_validator("path")
    @classmethod
    def normalize_path(cls, value: str | None) -> str | None:
        return _normalize_path(value)


class MockAIGenerateIn(BaseModel):
    project_id: int
    rule_ids: list[int] = Field(default_factory=list, max_length=20)
    requirement: str = Field(default="", max_length=4_000)
    rule_count: int = Field(default=1, ge=1, le=20)


class MockAIGeneratedRule(BaseModel):
    name: str = Field(min_length=1, max_length=128)
    method: MockMethod
    path: str
    status_code: int = Field(default=200, ge=100, le=599)
    response_headers: dict = Field(default_factory=dict)
    response_body: str | None = None
    match_conditions: MockMatchConditions = Field(default_factory=MockMatchConditions)
    delay_ms: int = Field(default=0, ge=0, le=30_000)
    is_enabled: bool = True
    render_template: bool = False
    record_requests: bool = False

    @field_validator("path")
    @classmethod
    def normalize_path(cls, value: str) -> str:
        return _normalize_path(value) or "/"


class MockAIGenerateOut(BaseModel):
    project_id: int
    rules: list[MockAIGeneratedRule]
    warnings: list[str] = Field(default_factory=list)


class MockRuleOut(BaseModel):
    id: int
    name: str
    project_id: int
    method: MockMethod
    path: str
    status_code: int
    response_headers: dict
    response_body: str | None
    match_conditions: dict
    delay_ms: int
    is_enabled: bool
    render_template: bool
    record_requests: bool
    version: int
    recorded_samples: list[dict]
    creator_id: int
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class MockRulesImportRequest(BaseModel):
    project_id: int
    rules: list[MockRuleCreate]


class MockRulesExportOut(BaseModel):
    project_id: int
    rules: list[MockRuleOut]


class MockRuleSnapshotOut(BaseModel):
    id: int
    rule_id: int
    version: int
    snapshot_data: dict
    note: str | None
    changed_by: int
    created_at: datetime

    model_config = {"from_attributes": True}


class PaginatedMockSnapshotsOut(BaseModel):
    items: list[MockRuleSnapshotOut]
    total: int
    page: int
    page_size: int


class MockRulePromoteSampleRequest(BaseModel):
    """录制样本转为新规则。"""

    sample_index: int = Field(..., ge=0, description="recorded_samples 中样本的下标")
    name: str | None = Field(default=None, description="新规则名，默认沿用原规则名 + (recorded)")
    enable: bool = Field(default=True, description="新规则是否启用")
