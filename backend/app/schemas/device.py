import re

from pydantic import BaseModel, Field, field_validator
from datetime import datetime
from typing import Literal
from app.models.device import DeviceStatus


class DeviceOut(BaseModel):
    id: int
    serial: str
    worker_id: str | None = None
    worker_hostname: str | None = None
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


class UnifiedDeviceOut(BaseModel):
    id: int
    platform: Literal["android", "ios"]
    name: str
    brand: str
    model: str
    identifier: str
    worker_id: str | None = None
    worker_hostname: str | None = None
    os_version: str
    status: Literal["online", "offline", "busy"]
    appium_server_url: str | None = None
    wda_local_port: int | None = None
    ip_address: str | None = None
    port: int | None = None
    last_seen_at: datetime | None = None
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


class DeviceScanItemOut(BaseModel):
    """多节点聚合扫描中单个节点的子任务状态。"""

    worker_id: str
    scan_id: str
    status: Literal["queued", "running", "completed", "failed", "timed_out"]
    count: int = 0
    error: str | None = None


class DeviceScanOut(BaseModel):
    """设备扫描结果；worker 模式下先返回 queued，再由状态接口返回最终列表。"""

    status: Literal["queued", "running", "completed", "partial_failed", "failed"]
    scan_id: str | None = None
    total_workers: int = 0
    completed_workers: int = 0
    failed_workers: int = 0
    items: list[DeviceScanItemOut] = Field(default_factory=list)
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
    instance_generation: int | None = None
    adb_ok: bool | None = None
    busy: bool | None = None
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
    worker_id: str | None = Field(default=None, max_length=128, description="目标 Android Worker 节点 ID")


class RemoteDeviceDisconnectIn(BaseModel):
    serial: str = Field(min_length=1, max_length=256, description="远程设备标识（格式 host:port）")
    device_id: int | None = Field(default=None, ge=1, description="目标设备 ID")
    worker_id: str | None = Field(default=None, max_length=128, description="目标 Android Worker 节点 ID")


class DeviceClaimIn(BaseModel):
    worker_id: str = Field(min_length=1, max_length=128, description="要认领到的 Android Worker 节点 ID")
    worker_hostname: str | None = Field(default=None, max_length=128)
    force: bool = Field(default=False, description="若已绑定其他节点，是否强制改绑（设备空闲时允许）")


class RemoteDeviceConnectOut(BaseModel):
    success: bool
    message: str
    serial: str
    device: DeviceOut | None = None


class DeviceKeyEventIn(BaseModel):
    keycode: str | int = Field(description="Android 按键码，如 3 (HOME), 4 (BACK), 26 (POWER)")

    @field_validator("keycode")
    @classmethod
    def _keycode_is_plain_token(cls, value: str | int) -> str | int:
        # 按键码会进入 adb shell 命令行，只接受数字或 KEYCODE_HOME 这类标识符
        if isinstance(value, bool) or (isinstance(value, int) and value < 0):
            raise ValueError("keycode 必须是非负整数或按键名")
        if isinstance(value, str) and not re.fullmatch(r"[A-Za-z0-9_]{1,64}", value.strip()):
            raise ValueError("keycode 只能包含字母、数字和下划线")
        return value


class DeviceTextInputIn(BaseModel):
    text: str = Field(min_length=1, max_length=1000, description="向设备输入的文本")


class DevicePackagesOut(BaseModel):
    device_id: int
    serial: str
    current_package: str | None = None
    current_activity: str | None = None
    packages: list[str] = Field(default_factory=list)
    read_at: datetime | None = None
    stale: bool = True
    source: str | None = None


class DevicePackageSnapshotOut(BaseModel):
    id: int
    device_id: int
    serial: str
    current_package: str | None = None
    current_activity: str | None = None
    packages: list[str] = Field(default_factory=list)
    source: str
    triggered_by: int | None = None
    read_at: datetime

    model_config = {"from_attributes": True}
