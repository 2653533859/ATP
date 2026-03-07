from pydantic import BaseModel
from datetime import datetime
from app.models.notification import NotifyChannel


class NotificationConfigCreate(BaseModel):
    name: str
    project_id: int
    channel: NotifyChannel
    config: dict = {}
    is_enabled: bool = True


class NotificationConfigUpdate(BaseModel):
    name: str | None = None
    channel: NotifyChannel | None = None
    config: dict | None = None
    is_enabled: bool | None = None


class NotificationConfigOut(BaseModel):
    id: int
    name: str
    project_id: int
    channel: NotifyChannel
    config: dict
    is_enabled: bool
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}
