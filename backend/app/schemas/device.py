from pydantic import BaseModel
from datetime import datetime
from app.models.device import DeviceStatus


class DeviceOut(BaseModel):
    id: int
    serial: str
    name: str | None
    model: str | None
    brand: str | None
    os_version: str | None
    sdk_version: str | None
    resolution: str | None
    status: DeviceStatus
    ip_address: str | None
    port: int | None
    description: str | None
    last_seen_at: datetime | None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class DeviceUpdate(BaseModel):
    name: str | None = None
    description: str | None = None
    ip_address: str | None = None
    port: int | None = None
