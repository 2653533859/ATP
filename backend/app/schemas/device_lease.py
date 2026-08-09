from datetime import datetime

from pydantic import BaseModel, Field


class DeviceLeaseAcquireIn(BaseModel):
    ttl_seconds: int = Field(default=900, ge=30, le=7200)
    owner_label: str = Field(default="manual", min_length=1, max_length=128)


class DeviceLeaseTokenIn(BaseModel):
    lease_token: str = Field(min_length=16, max_length=96)


class DeviceLeaseOut(BaseModel):
    device_id: int
    owner_id: int | None
    owner_label: str
    acquired_at: datetime
    heartbeat_at: datetime
    expires_at: datetime
    lease_token: str | None = None

    model_config = {"from_attributes": True}
