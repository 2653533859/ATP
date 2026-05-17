from pydantic import BaseModel, Field
from datetime import datetime
from app.models.suite import SuiteStatus, SuiteRunStatus


class SuiteCaseItem(BaseModel):
    case_id: int
    sort: int = 0


class TestSuiteCreate(BaseModel):
    name: str
    description: str | None = None
    project_id: int
    case_ids: list[SuiteCaseItem] = Field(default_factory=list)
    parameterization: dict | None = None
    config: dict = Field(default_factory=dict)


class TestSuiteUpdate(BaseModel):
    name: str | None = None
    description: str | None = None
    case_ids: list[SuiteCaseItem] | None = None
    parameterization: dict | None = None
    config: dict | None = None
    status: SuiteStatus | None = None


class TestSuiteOut(BaseModel):
    id: int
    name: str
    description: str | None
    project_id: int
    status: SuiteStatus
    creator_id: int
    case_ids: list[dict]
    parameterization: dict | None
    config: dict
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class SuiteRunTrigger(BaseModel):
    env_id: int | None = None
    extra_vars: dict = Field(default_factory=dict)


class SuiteRunOut(BaseModel):
    id: int
    suite_id: int
    triggered_by: int
    trace_id: str | None = None
    status: SuiteRunStatus
    environment: str | None
    duration_ms: int | None
    error_message: str | None
    result_summary: dict
    case_run_ids: list[dict]
    created_at: datetime

    model_config = {"from_attributes": True}
