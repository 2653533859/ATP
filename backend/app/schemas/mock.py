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


class MockMatchConditions(BaseModel):
    query: dict[str, str] = Field(default_factory=dict)
    headers: dict[str, str] = Field(default_factory=dict)
    body: dict[str, str] = Field(default_factory=dict)


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
    match_conditions: MockMatchConditions | None = None
    delay_ms: int | None = None
    is_enabled: bool | None = None
    render_template: bool | None = None
    record_requests: bool | None = None

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
