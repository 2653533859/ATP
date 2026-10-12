"""远程设备接入（网络 ADB 直连与断开）功能回归测试。

覆盖：
1. adb_service 中的 connect_remote_device 成功与失败解析；
2. adb_service 中的 disconnect_remote_device 解析；
3. POST /devices/connect 接入成功自动扫描同步设备与失败 400 校验；
4. POST /devices/disconnect 远程断开连接与状态收敛。
"""

from datetime import datetime, timezone
from unittest.mock import AsyncMock

import pytest
from fastapi import HTTPException

from app.models.bootstrap import load_all_models
from app.models.device import Device, DeviceStatus
from app.models.user import User
from app.schemas.device import RemoteDeviceConnectIn, RemoteDeviceDisconnectIn
from app.services.adb_service import connect_remote_device, disconnect_remote_device

load_all_models()


# ==================== 1. adb_service 远程连接命令解析 ====================


def test_connect_remote_device_success_parsing(monkeypatch):
    from app.services import adb_service

    monkeypatch.setattr(adb_service, "_run_adb", lambda *args, **kwargs: "connected to 192.168.1.100:5555")

    success, msg = connect_remote_device("192.168.1.100", 5555)
    assert success is True
    assert "connected to" in msg


def test_connect_remote_device_failure_parsing(monkeypatch):
    from app.services import adb_service

    monkeypatch.setattr(
        adb_service,
        "_run_adb",
        lambda *args, **kwargs: "cannot connect to 192.168.1.100:5555: No connection could be made",
    )

    success, msg = connect_remote_device("192.168.1.100", 5555)
    assert success is False
    assert "cannot connect" in msg


def test_disconnect_remote_device_parsing(monkeypatch):
    from app.services import adb_service

    monkeypatch.setattr(adb_service, "_run_adb", lambda *args, **kwargs: "disconnected 192.168.1.100:5555")

    success, msg = disconnect_remote_device("192.168.1.100:5555")
    assert success is True
    assert "disconnected" in msg


# ==================== 2. API 端点测试 ====================


@pytest.mark.asyncio
async def test_api_connect_remote_device_success(monkeypatch):
    from app.api.v1 import devices

    now = datetime.now(timezone.utc)
    mock_device = Device(
        id=99,
        serial="192.168.3.150:5555",
        status=DeviceStatus.online,
        model="Remote-Phone",
        brand="Google",
        os_version="13",
        created_at=now,
        updated_at=now,
    )

    class FakeDB:
        async def commit(self):
            pass

        async def scalar(self, stmt):
            return mock_device

    monkeypatch.setattr(
        devices,
        "async_connect_remote_device",
        AsyncMock(return_value=(True, "connected to 192.168.3.150:5555")),
    )
    monkeypatch.setattr(devices, "async_scan_devices", AsyncMock(return_value=[]))
    monkeypatch.setattr(devices, "sync_devices_to_db_async", AsyncMock())

    body = RemoteDeviceConnectIn(host="192.168.3.150", port=5555)
    res = await devices.connect_remote_adb_device(body=body, db=FakeDB(), _=User(id=1, username="engineer"))

    assert res.success is True
    assert res.serial == "192.168.3.150:5555"
    assert res.device is not None
    assert res.device.serial == "192.168.3.150:5555"


@pytest.mark.asyncio
async def test_api_connect_remote_device_failure(monkeypatch):
    from app.api.v1 import devices

    monkeypatch.setattr(
        devices,
        "async_connect_remote_device",
        AsyncMock(return_value=(False, "Connection timed out")),
    )

    class FakeDB:
        pass

    body = RemoteDeviceConnectIn(host="10.255.255.1", port=5555)
    with pytest.raises(HTTPException) as exc_info:
        await devices.connect_remote_adb_device(body=body, db=FakeDB(), _=User(id=1, username="engineer"))

    assert exc_info.value.status_code == 400
    assert "远程设备连接失败" in exc_info.value.detail


@pytest.mark.asyncio
async def test_api_disconnect_remote_device(monkeypatch):
    from app.api.v1 import devices

    now = datetime.now(timezone.utc)
    mock_device = Device(
        id=99,
        serial="192.168.3.150:5555",
        status=DeviceStatus.online,
        created_at=now,
        updated_at=now,
    )

    class FakeDB:
        async def commit(self):
            pass

        async def scalar(self, stmt):
            return mock_device

    monkeypatch.setattr(
        devices,
        "async_disconnect_remote_device",
        AsyncMock(return_value=(True, "disconnected 192.168.3.150:5555")),
    )
    monkeypatch.setattr(devices, "async_scan_devices", AsyncMock(return_value=None))

    body = RemoteDeviceDisconnectIn(serial="192.168.3.150:5555")
    res = await devices.disconnect_remote_adb_device(body=body, db=FakeDB(), _=User(id=1, username="engineer"))

    assert res["success"] is True
    assert res["serial"] == "192.168.3.150:5555"
    assert mock_device.status == DeviceStatus.offline
