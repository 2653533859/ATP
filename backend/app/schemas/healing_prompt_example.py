from datetime import datetime

from pydantic import BaseModel, Field


class HealingPromptExampleOut(BaseModel):
    id: int
    error_fingerprint: str
    case_type: str
    step_context_json: dict
    suggestion_text: str
    source_step_result_id: int | None = None
    marked_high_quality: bool
    marked_by: int | None = None
    marked_at: datetime | None = None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class HealingPromptExampleUpdateIn(BaseModel):
    marked_high_quality: bool | None = None
    suggestion_text: str | None = Field(default=None, min_length=1)
