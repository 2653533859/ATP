from datetime import datetime

from pydantic import BaseModel, Field

from app.schemas.case import TestRunOut
from app.schemas.plan import PlanRunOut
from app.schemas.suite import SuiteRunOut


class TraceDetailOut(BaseModel):
    trace_id: str
    total_runs: int
    created_at: datetime | None = None
    last_seen_at: datetime | None = None
    case_runs: list[TestRunOut] = Field(default_factory=list)
    suite_runs: list[SuiteRunOut] = Field(default_factory=list)
    plan_runs: list[PlanRunOut] = Field(default_factory=list)
