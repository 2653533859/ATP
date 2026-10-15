"""Device Agents 远程接入点 API 与反向隧道管理测试。

覆盖：
1. GET /api/v1/device-agents/ 接入点列表与链路指标查询；
2. GET /api/v1/device-agents/agent-script 脚本下载；
3. POST /api/v1/device-agents/{id}/link-probe 带宽探测；
4. DELETE /api/v1/device-agents/{id} 离线接入点删除与端口释放、在线防误删（400）；
5. WebSocket Token 鉴权（_authenticate_ws_token）。
"""

from unittest.mock import AsyncMock, MagicMock
import pytest
from fastapi import HTTPException
from starlette.websockets import WebSocket

from app.models.bootstrap import load_all_models
from app.models.device_agent import RemoteAgent, RemoteAgentDevice
from app.models.user import User

load_all_models()


# ==================== 1. 接入点列表与下载脚本 ====================


def test_list_device_agents_returns_items(monkeypatch):
    from app.api.v1 import device_agents

    mock_items = [
        {
            "id": 1,
            "name": "工位B",
            "status": "ONLINE",
            "device_count": 2,
            "online_device_count": 2,
            "devices": [],
        }
    ]
    monkeypatch.setattr(device_agents.tunnel_hub, "list_agents", lambda: mock_items)

    user = User(id=1, username="tester")
    res = device_agents.list_device_agents(current_user=user)
    assert res == {"items": mock_items}


def test_download_agent_script_returns_file(monkeypatch, tmp_path):
    from app.api.v1 import device_agents

    fake_script = tmp_path / "device_agent.py"
    fake_script.write_text("#!/usr/bin/env python3\nprint('agent')", encoding="utf-8")
    monkeypatch.setattr(device_agents, "AGENT_SCRIPT_PATH", fake_script)

    user = User(id=1, username="tester")
    response = device_agents.download_agent_script(current_user=user)
    assert response.status_code == 200
    assert response.filename == "device_agent.py"


# ==================== 2. 带宽探测与删除接入点 ====================


@pytest.mark.asyncio
async def test_probe_agent_bandwidth(monkeypatch):
    from app.api.v1 import device_agents

    mock_probe = {"bps": 20_000_000, "bytes": 1_000_000, "elapsed_ms": 400, "at": "2026-10-12T16:00:00"}
    monkeypatch.setattr(device_agents.tunnel_hub, "probe_agent_bandwidth", AsyncMock(return_value=mock_probe))

    user = User(id=1, username="tester")
    res = await device_agents.probe_device_agent_link(agent_id=1, current_user=user)
    assert res["bps"] == 20_000_000


def test_delete_device_agent_rejects_online_agent(monkeypatch):
    from app.api.v1 import device_agents

    agent = RemoteAgent(id=1, name="工位B", status="ONLINE")

    class FakeSession:
        def __enter__(self):
            return self

        def __exit__(self, *args):
            pass

        def scalar(self, stmt):
            return agent

    monkeypatch.setattr(device_agents, "Session", lambda *args: FakeSession())
    monkeypatch.setattr(device_agents.tunnel_hub, "is_agent_online", lambda name: True)

    user = User(id=1, username="tester")
    with pytest.raises(HTTPException) as exc_info:
        device_agents.delete_device_agent(agent_id=1, current_user=user)
    assert exc_info.value.status_code == 400
    assert "在线" in exc_info.value.detail


# ==================== 3. WebSocket 鉴权解析 ====================


def test_authenticate_ws_token():
    from app.api.v1 import device_agents
    from app.core.config import settings

    # 1. Bearer Token 格式有效
    ws_mock = MagicMock(spec=WebSocket)
    ws_mock.headers = {"authorization": f"Bearer {settings.APP_SECRET_KEY}"}
    ws_mock.query_params = {}
    assert device_agents._authenticate_ws_token(ws_mock) == "admin"

    # 2. Query 参数 Token 格式有效
    ws_mock_query = MagicMock(spec=WebSocket)
    ws_mock_query.headers = {}
    ws_mock_query.query_params = {"token": settings.APP_SECRET_KEY}
    assert device_agents._authenticate_ws_token(ws_mock_query) == "admin"


# ==================== 4. 远程设备自动入池与状态收敛 ====================


def test_tunnel_hub_syncs_devices_to_central_pool(monkeypatch):
    import sys
    from app.device_agents.protocol import tunnel_serial
    from app.models.device import Device, DeviceStatus

    th_module = sys.modules["app.device_agents.tunnel_hub"]

    saved_entities = []

    class FakeSession:
        def __enter__(self):
            return self

        def __exit__(self, *args):
            pass

        def scalars(self, stmt):
            class _Res:
                def all(self):
                    return []

                def first(self):
                    return None

            return _Res()

        def scalar(self, stmt):
            return None

        def add(self, entity):
            saved_entities.append(entity)

        def commit(self):
            pass

    monkeypatch.setattr(th_module, "Session", lambda *args: FakeSession())
    tunnel_hub = th_module.tunnel_hub

    reported = {
        "usb_serial_01": {
            "model": "Pixel 7",
            "brand": "Google",
            "os_version": "14",
        }
    }

    port_map, errors = tunnel_hub._persist_device_mappings(agent_id=10, reported=reported)
    assert "usb_serial_01" in port_map
    assert not errors

    mapping = next(e for e in saved_entities if isinstance(e, RemoteAgentDevice))
    device = next(e for e in saved_entities if isinstance(e, Device))

    assert mapping.usb_serial == "usb_serial_01"
    assert device.serial == tunnel_serial(mapping.tunnel_port)
    assert device.model == "Pixel 7"
    assert device.brand == "Google"
    assert device.status == DeviceStatus.online


def test_tunnel_hub_persist_agent_offline_marks_devices_offline(monkeypatch):
    import sys
    from app.device_agents.protocol import tunnel_serial
    from app.models.device import Device, DeviceStatus

    th_module = sys.modules["app.device_agents.tunnel_hub"]

    mock_agent = RemoteAgent(id=10, name="Agent-10", status="ONLINE")
    mock_mapping = RemoteAgentDevice(id=1, agent_id=10, usb_serial="usb_01", tunnel_port=28105)
    mock_dev = Device(id=1, serial=tunnel_serial(28105), status=DeviceStatus.online)

    class FakeSession:
        def __enter__(self):
            return self

        def __exit__(self, *args):
            pass

        def scalar(self, stmt):
            sql = str(stmt).lower()
            if "remote_agents" in sql:
                return mock_agent
            return None

        def scalars(self, stmt):
            class _Res:
                def __init__(self, items):
                    self._items = items

                def all(self):
                    return self._items

            sql = str(stmt).lower()
            if "remote_agent_devices" in sql:
                return _Res([mock_mapping])
            if "devices" in sql:
                return _Res([mock_dev])
            return _Res([])

        def add(self, entity):
            pass

        def commit(self):
            pass

    monkeypatch.setattr(th_module, "Session", lambda *args: FakeSession())
    tunnel_hub = th_module.tunnel_hub
    tunnel_hub._persist_agent_offline(agent_id=10)
    assert mock_agent.status == "OFFLINE"
    assert mock_dev.status == DeviceStatus.offline
