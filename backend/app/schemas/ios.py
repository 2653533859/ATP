"""Schemas for iOS device and IPA asset management."""

from datetime import datetime

from pydantic import AnyHttpUrl, BaseModel, Field

from app.models.ios import IosDeviceStatus


class IosDeviceCreate(BaseModel):
    udid: str = Field(min_length=1, max_length=256)
    name: str | None = Field(default=None, max_length=128)
    model: str | None = Field(default=None, max_length=128)
    platform_version: str | None = Field(default=None, max_length=32)
    appium_server_url: AnyHttpUrl = AnyHttpUrl("http://127.0.0.1:4723")
    wda_local_port: int | None = Field(default=None, ge=1, le=65535)
    ip_address: str | None = Field(default=None, max_length=64)
    port: int | None = Field(default=None, ge=1, le=65535)
    description: str | None = None


class IosDeviceUpdate(BaseModel):
    name: str | None = Field(default=None, max_length=128)
    model: str | None = Field(default=None, max_length=128)
    platform_version: str | None = Field(default=None, max_length=32)
    status: IosDeviceStatus | None = None
    appium_server_url: AnyHttpUrl | None = None
    wda_local_port: int | None = Field(default=None, ge=1, le=65535)
    ip_address: str | None = Field(default=None, max_length=64)
    port: int | None = Field(default=None, ge=1, le=65535)
    description: str | None = None


class IosDeviceOut(BaseModel):
    id: int
    udid: str
    name: str | None
    model: str | None
    platform_version: str | None
    status: IosDeviceStatus
    appium_server_url: str
    wda_local_port: int | None
    ip_address: str | None
    port: int | None
    description: str | None
    last_seen_at: datetime | None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class IosAppOut(BaseModel):
    id: int
    project_id: int
    filename: str
    bundle_id: str | None
    version_name: str | None
    file_size: int
    object_name: str
    signing_identity: str | None
    provisioning_profile: str | None
    description: str | None
    uploaded_by: int
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class IosAppUpdate(BaseModel):
    bundle_id: str | None = Field(default=None, max_length=256)
    version_name: str | None = Field(default=None, max_length=64)
    signing_identity: str | None = Field(default=None, max_length=256)
    provisioning_profile: str | None = Field(default=None, max_length=256)
    description: str | None = None
