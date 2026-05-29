from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class UserSettingUpdateIn(BaseModel):
    value: dict[str, Any] = Field(default_factory=dict)


class UserSettingOut(BaseModel):
    key: str
    value: dict[str, Any]
    updated_at: datetime | None = None

    model_config = {"from_attributes": True}
