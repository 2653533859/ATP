from pydantic import BaseModel, Field
from datetime import datetime
from typing import Literal
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


class DeviceGroupSave(BaseModel):
    name: str = Field(min_length=1, max_length=128)
    description: str | None = Field(default=None, max_length=1000)
    device_ids: list[int] = Field(default_factory=list, max_length=200)


class DeviceGroupOut(BaseModel):
    id: int
    name: str
    description: str | None
    devices: list[DeviceOut]
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class DeviceScanOut(BaseModel):
    """设备扫描结果；worker 模式下先返回 queued，再由状态接口返回最终列表。"""

    status: Literal["queued", "running", "completed", "failed"]
    scan_id: str | None = None
    devices: list[DeviceOut] = Field(default_factory=list)
    error: str | None = None


class AndroidWorkerOut(BaseModel):
    """在线 Android Worker 的 Redis 心跳快照。"""

    worker_id: str
    status: Literal["online"]
    queues: list[str] = Field(default_factory=list)
    capabilities: list[str] = Field(default_factory=list)
    hostname: str | None = None
    pid: int | None = None
    updated_at: float
    expires_at: float


class DeviceTapIn(BaseModel):
    x: int
    y: int


class DeviceSwipeIn(BaseModel):
    x1: int
    y1: int
    x2: int
    y2: int
    duration_ms: int = 300


class RemoteDeviceConnectIn(BaseModel):
    host: str = Field(min_length=1, max_length=256, description="远程设备 IP 或主机名")
    port: int = Field(default=5555, ge=1, le=65535, description="ADB 网络调试端口，默认 5555")


class RemoteDeviceDisconnectIn(BaseModel):
    serial: str = Field(min_length=1, max_length=256, description="远程设备标识（格式 host:port）")


class RemoteDeviceConnectOut(BaseModel):
    success: bool
    message: str
    serial: str
    device: DeviceOut | None = None


class DeviceKeyEventIn(BaseModel):
    keycode: str | int = Field(description="Android 按键码，如 3 (HOME), 4 (BACK), 26 (POWER)")


class DeviceTextInputIn(BaseModel):
    text: str = Field(min_length=1, max_length=1000, description="向设备输入的文本")
