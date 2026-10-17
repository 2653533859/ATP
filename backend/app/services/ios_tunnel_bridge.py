"""iOS 设备 WDA 反向 WebSocket 隧道与端口分配器服务 (T1.1)

解决跨网络物理机 iPhone 自动化执行受限问题:
通过反向 WebSocket 隧道将远端 macOS Worker / 物理机上的 WebDriverAgent (8100端口)
透明映射并代理至 ATP 服务端动态隧道端口 (8200~8299),
使平台、Appium 执行器与远程控制模块可直接通过 127.0.0.1:<tunnel_port> 操纵 iPhone。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional


@dataclass
class IosTunnelSession:
    udid: str
    device_name: str
    model: str
    ios_version: str
    agent_id: str
    agent_name: str
    remote_wda_port: int  # 远端真实 WDA 端口 (通常为 8100)
    local_tunnel_port: int  # 本地动态映射端口 (8200~8299)
    status: str  # CONNECTED | DISCONNECTED | BUSY
    total_requests_forwarded: int = 0
    connected_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    last_activity_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def to_dict(self) -> Dict[str, Any]:
        return {
            "udid": self.udid,
            "device_name": self.device_name,
            "model": self.model,
            "ios_version": self.ios_version,
            "agent_id": self.agent_id,
            "agent_name": self.agent_name,
            "remote_wda_port": self.remote_wda_port,
            "local_tunnel_port": self.local_tunnel_port,
            "status": self.status,
            "total_requests_forwarded": self.total_requests_forwarded,
            "connected_at": self.connected_at,
            "last_activity_at": self.last_activity_at,
        }


# 全局轻量级活跃 iOS 隧道会话池
_ACTIVE_IOS_TUNNELS: Dict[str, IosTunnelSession] = {}

# 动态隧道端口范围
_TUNNEL_PORT_START = 8200
_TUNNEL_PORT_END = 8299


def clear_ios_tunnels() -> None:
    _ACTIVE_IOS_TUNNELS.clear()


def list_active_ios_tunnels() -> List[Dict[str, Any]]:
    return [t.to_dict() for t in _ACTIVE_IOS_TUNNELS.values()]


def get_ios_tunnel(udid: str) -> Optional[IosTunnelSession]:
    return _ACTIVE_IOS_TUNNELS.get(udid)


def _allocate_available_tunnel_port() -> int:
    """寻找并分配未被占用的本地隧道端口"""
    used_ports = {t.local_tunnel_port for t in _ACTIVE_IOS_TUNNELS.values()}
    for port in range(_TUNNEL_PORT_START, _TUNNEL_PORT_END + 1):
        if port not in used_ports:
            return port
    raise RuntimeError("所有 iOS WDA 隧道端口 (8200~8299) 均已被分配耗尽")


def register_ios_tunnel(
    udid: str,
    device_name: str,
    model: str,
    ios_version: str,
    agent_id: str,
    agent_name: str,
    remote_wda_port: int = 8100,
    preferred_local_port: int | None = None,
) -> IosTunnelSession:
    """注册或复用一台真实 iPhone 的反向隧道映射会话"""
    now_iso = datetime.now(timezone.utc).isoformat()

    # 若已存在活跃会话，更新并复用端口
    if udid in _ACTIVE_IOS_TUNNELS:
        session = _ACTIVE_IOS_TUNNELS[udid]
        session.device_name = device_name
        session.model = model
        session.ios_version = ios_version
        session.agent_id = agent_id
        session.agent_name = agent_name
        session.status = "CONNECTED"
        session.last_activity_at = now_iso
        return session

    local_port = preferred_local_port or _allocate_available_tunnel_port()

    session = IosTunnelSession(
        udid=udid,
        device_name=device_name,
        model=model,
        ios_version=ios_version,
        agent_id=agent_id,
        agent_name=agent_name,
        remote_wda_port=remote_wda_port,
        local_tunnel_port=local_port,
        status="CONNECTED",
        connected_at=now_iso,
        last_activity_at=now_iso,
    )
    _ACTIVE_IOS_TUNNELS[udid] = session
    return session


def release_ios_tunnel(udid: str) -> bool:
    """断开并回收指定 iPhone 设备的隧道连接"""
    if udid in _ACTIVE_IOS_TUNNELS:
        del _ACTIVE_IOS_TUNNELS[udid]
        return True
    return False


def simulate_forward_wda_command(
    udid: str,
    command_path: str,
    _method: str = "GET",
    params: Dict[str, Any] | None = None,
) -> Dict[str, Any]:
    """模拟向已建立隧道的 iPhone WDA 下发指令并接收回传数据"""
    session = get_ios_tunnel(udid)
    if not session:
        raise ValueError(f"未找到设备 UDID [{udid}] 的活跃 WDA 隧道会话，设备可能已离线")

    session.total_requests_forwarded += 1
    session.last_activity_at = datetime.now(timezone.utc).isoformat()

    # 规范化模拟基础 WDA 响应
    cmd_lower = command_path.lower()
    if "status" in cmd_lower:
        return {
            "value": {
                "state": "success",
                "os": {"name": "iOS", "version": session.ios_version},
                "device": session.model,
                "ready": True,
            },
            "sessionId": f"wda_sess_{udid[:8]}",
        }
    if "screenshot" in cmd_lower:
        return {
            "value": "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNk+M9QDwADhgGAWjR9awAAAABJRU5ErkJggg==",
            "sessionId": f"wda_sess_{udid[:8]}",
        }
    if "homescreen" in cmd_lower:
        return {
            "value": None,
            "sessionId": f"wda_sess_{udid[:8]}",
        }

    return {
        "value": {"result": "success", "echo_params": params or {}},
        "sessionId": f"wda_sess_{udid[:8]}",
    }
