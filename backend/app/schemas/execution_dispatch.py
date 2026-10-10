"""Public dispatch metadata; encrypted arguments and claim tokens stay private."""

from datetime import datetime

from pydantic import BaseModel


class ExecutionDispatchOut(BaseModel):
    id: str
    run_id: int
    mode: str
    queue: str
    status: str
    attempt_count: int
    error_code: str | None
    claimed_at: datetime | None
    submitted_at: datetime | None
    accepted_at: datetime | None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}
