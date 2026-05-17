from datetime import datetime
from pydantic import BaseModel, ConfigDict, Field


class StoragePolicyOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    prefix: str
    retention_days: int
    max_size_gb: float | None = None
    enabled: bool
    description: str | None = None
    created_at: datetime
    updated_at: datetime


class StoragePolicyCreateIn(BaseModel):
    name: str = Field(min_length=1, max_length=64)
    prefix: str = Field(min_length=1, max_length=128)
    retention_days: int = Field(default=30, ge=1, le=3650)
    max_size_gb: float | None = Field(default=None, ge=0)
    enabled: bool = True
    description: str | None = Field(default=None, max_length=2048)


class StoragePolicyUpdateIn(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=64)
    prefix: str | None = Field(default=None, min_length=1, max_length=128)
    retention_days: int | None = Field(default=None, ge=1, le=3650)
    max_size_gb: float | None = Field(default=None, ge=0)
    enabled: bool | None = None
    description: str | None = Field(default=None, max_length=2048)
