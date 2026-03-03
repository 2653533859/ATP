from pydantic import BaseModel
from datetime import datetime
from app.models.case import CaseType, RunStatus


# ── TestCase ─────────────────────────────────────────────
class TestCaseCreate(BaseModel):
    name: str
    description: str | None = None
    case_type: CaseType
    module_id: int
    tags: list[str] = []
    config: dict = {}


class TestCaseUpdate(BaseModel):
    name: str | None = None
    description: str | None = None
    tags: list[str] | None = None
    config: dict | None = None


class TestCaseOut(BaseModel):
    id: int
    name: str
    description: str | None
    case_type: CaseType
    status: str
    tags: list[str]
    module_id: int
    creator_id: int
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


# ── TestRun ──────────────────────────────────────────────
class RunTriggerRequest(BaseModel):
    environment: str | None = None
    extra_vars: dict = {}


class StepResultOut(BaseModel):
    id: int
    step_index: int
    name: str
    status: RunStatus
    duration_ms: int | None
    request_data: dict | None
    response_data: dict | None
    screenshot_url: str | None
    error_message: str | None

    model_config = {"from_attributes": True}


class TestRunOut(BaseModel):
    id: int
    case_id: int
    triggered_by: int
    status: RunStatus
    environment: str | None
    duration_ms: int | None
    error_message: str | None
    result_summary: dict
    created_at: datetime
    steps: list[StepResultOut] = []

    model_config = {"from_attributes": True}
