from pydantic import BaseModel, Field
from datetime import datetime
from app.models.plan import PlanStatus, ScheduleType, TriggerType, PlanRunStatus


class PlanSuiteItem(BaseModel):
    suite_id: int
    sort: int = 0


class TestPlanCreate(BaseModel):
    name: str
    description: str | None = None
    project_id: int
    suite_ids: list[PlanSuiteItem] = Field(default_factory=list)
    schedule_type: ScheduleType = ScheduleType.manual
    cron_expression: str | None = None
    is_enabled: bool = True
    auto_create_bugs: bool = False
    env_id: int | None = None
    config: dict = Field(default_factory=dict)


class TestPlanUpdate(BaseModel):
    name: str | None = None
    description: str | None = None
    suite_ids: list[PlanSuiteItem] | None = None
    schedule_type: ScheduleType | None = None
    cron_expression: str | None = None
    is_enabled: bool | None = None
    auto_create_bugs: bool | None = None
    env_id: int | None = None
    status: PlanStatus | None = None
    config: dict | None = None


class TestPlanOut(BaseModel):
    id: int
    name: str
    description: str | None
    project_id: int
    status: PlanStatus
    creator_id: int
    suite_ids: list[dict]
    schedule_type: ScheduleType
    cron_expression: str | None
    webhook_secret: str | None
    is_enabled: bool
    auto_create_bugs: bool
    env_id: int | None
    config: dict = Field(default_factory=dict)
    last_run_at: datetime | None
    next_run_at: datetime | None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class PlanRunTrigger(BaseModel):
    env_id: int | None = None
    extra_vars: dict = Field(default_factory=dict)


class WebhookTriggerRequest(BaseModel):
    plan_id: int
    extra_vars: dict = Field(default_factory=dict)


class PlanRunOut(BaseModel):
    id: int
    plan_id: int
    triggered_by: int | None
    trace_id: str | None = None
    trigger_type: TriggerType
    status: PlanRunStatus
    duration_ms: int | None
    error_message: str | None
    suite_run_ids: list[dict]
    result_summary: dict
    created_at: datetime

    model_config = {"from_attributes": True}


class PlanBatchDeleteIn(BaseModel):
    plan_ids: list[int] = Field(min_length=1, max_length=200)


class PlanBatchToggleIn(BaseModel):
    plan_ids: list[int] = Field(min_length=1, max_length=200)
    is_enabled: bool


class PlanBatchOpOut(BaseModel):
    requested: int
    processed: int
    skipped_ids: list[int] = Field(default_factory=list)
