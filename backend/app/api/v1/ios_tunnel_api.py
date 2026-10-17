"""iOS 设备反向 WebSocket 隧道与状态管理 API (T1.3)"""

from __future__ import annotations

from typing import Any, Dict, List, Optional
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from app.api.deps import require_engineer
from app.models.user import User
from app.services.ios_device_heartbeat_keeper import (
    get_heartbeat_record,
    list_heartbeat_records,
    record_ios_heartbeat,
    sweep_ios_heartbeats,
    trigger_wda_self_healing,
)
from app.services.ios_tunnel_bridge import (
    get_ios_tunnel,
    list_active_ios_tunnels,
    register_ios_tunnel,
    release_ios_tunnel,
    simulate_forward_wda_command,
)

router = APIRouter(prefix="/ios/tunnel", tags=["iOS Tunnel"])


class RegisterIosTunnelRequest(BaseModel):
    udid: str = Field(..., description="物理 iPhone 设备唯一 UDID")
    device_name: str = Field(..., description="设备名称 (如 iPhone 15 Pro)")
    model: str = Field(..., description="内部机型标识 (如 iPhone16,1)")
    ios_version: str = Field(..., description="iOS 系统版本号 (如 17.5.1)")
    agent_id: str = Field(..., description="远端 macOS Agent 唯一标识")
    agent_name: str = Field(..., description="远端 macOS Agent 机器名称")
    remote_wda_port: int = Field(8100, description="远端 WDA 监听端口")
    preferred_local_port: Optional[int] = Field(None, description="期望分配的本地端口")


class RecordHeartbeatRequest(BaseModel):
    udid: str = Field(..., description="设备唯一 UDID")
    agent_id: str = Field(..., description="所属 Agent ID")
    battery_level: int = Field(100, ge=0, le=100, description="电池电量百分比")
    battery_charging: bool = Field(True, description="是否处于充电状态")
    temperature_celsius: float = Field(28.5, description="设备电池温度")
    wda_alive: bool = Field(True, description="WebDriverAgent 探针是否存活")


class ForwardWdaCommandRequest(BaseModel):
    udid: str = Field(..., description="目标设备 UDID")
    command_path: str = Field(..., description="WDA REST 相对路径 (如 /status 或 /screenshot)")
    method: str = Field("GET", description="HTTP 请求方法")
    params: Dict[str, Any] = Field(default_factory=dict, description="指令参数载荷")


class HealWdaRequest(BaseModel):
    udid: str = Field(..., description="目标设备 UDID")


class SweepHeartbeatsRequest(BaseModel):
    timeout_seconds: float = Field(15.0, description="心跳超时判定阈值 (秒)")


@router.post("/register")
def register_tunnel_endpoint(
    payload: RegisterIosTunnelRequest,
    _user: User = Depends(require_engineer),
) -> Dict[str, Any]:
    """注册一台物理 iPhone 的反向隧道并分配映射端口"""
    session = register_ios_tunnel(
        udid=payload.udid,
        device_name=payload.device_name,
        model=payload.model,
        ios_version=payload.ios_version,
        agent_id=payload.agent_id,
        agent_name=payload.agent_name,
        remote_wda_port=payload.remote_wda_port,
        preferred_local_port=payload.preferred_local_port,
    )
    # 自动关联心跳注册
    record_ios_heartbeat(
        udid=payload.udid,
        agent_id=payload.agent_id,
        wda_alive=True,
    )
    return {
        "message": f"iOS 设备 [{payload.device_name}] 反向隧道建立成功",
        "tunnel": session.to_dict(),
    }


@router.post("/heartbeat")
def heartbeat_endpoint(
    payload: RecordHeartbeatRequest,
    _user: User = Depends(require_engineer),
) -> Dict[str, Any]:
    """接收来自 Agent 的物理 iPhone 心跳探针上报"""
    rec = record_ios_heartbeat(
        udid=payload.udid,
        agent_id=payload.agent_id,
        battery_level=payload.battery_level,
        battery_charging=payload.battery_charging,
        temperature_celsius=payload.temperature_celsius,
        wda_alive=payload.wda_alive,
    )
    return {
        "message": "心跳已更新",
        "heartbeat": rec.to_dict(),
    }


@router.get("/devices")
def list_devices_endpoint(
    _user: User = Depends(require_engineer),
) -> Dict[str, Any]:
    """列出全部通过隧道连接的 iOS 真机设备与其心跳状态"""
    tunnels = list_active_ios_tunnels()
    heartbeats = {r["udid"]: r for r in list_heartbeat_records()}

    merged: List[Dict[str, Any]] = []
    for t in tunnels:
        item = dict(t)
        hb = heartbeats.get(t["udid"])
        item["battery_level"] = hb.get("battery_level", 100) if hb else 100
        item["temperature_celsius"] = hb.get("temperature_celsius", 28.0) if hb else 28.0
        item["wda_alive"] = hb.get("wda_alive", True) if hb else True
        item["health_status"] = hb.get("status", "ONLINE") if hb else "ONLINE"
        merged.append(item)

    return {
        "total": len(merged),
        "devices": merged,
    }


@router.get("/device/{udid}")
def get_device_endpoint(
    udid: str,
    _user: User = Depends(require_engineer),
) -> Dict[str, Any]:
    """查询单台物理 iPhone 隧道会话详情"""
    session = get_ios_tunnel(udid)
    if not session:
        raise HTTPException(status_code=404, detail="未找到目标设备的活跃反向隧道")
    hb = get_heartbeat_record(udid)
    res = session.to_dict()
    res["heartbeat"] = hb.to_dict() if hb else None
    return {"device": res}


@router.post("/wda/forward")
def forward_wda_endpoint(
    payload: ForwardWdaCommandRequest,
    _user: User = Depends(require_engineer),
) -> Dict[str, Any]:
    """通过反向隧道向 iPhone 设备的 WDA 代理下发指令"""
    try:
        wda_res = simulate_forward_wda_command(
            udid=payload.udid,
            command_path=payload.command_path,
            method=payload.method,
            params=payload.params,
        )
        return {
            "udid": payload.udid,
            "command": payload.command_path,
            "response": wda_res,
        }
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/wda/heal")
def heal_wda_endpoint(
    payload: HealWdaRequest,
    _user: User = Depends(require_engineer),
) -> Dict[str, Any]:
    """触发 WDA 异常自愈重启"""
    try:
        res = trigger_wda_self_healing(payload.udid)
        return res
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.post("/sweep")
def sweep_heartbeats_endpoint(
    payload: SweepHeartbeatsRequest,
    _user: User = Depends(require_engineer),
) -> Dict[str, Any]:
    """执行全部真机的心跳保活巡检，超时失联标记为 OFFLINE"""
    offline_udids = sweep_ios_heartbeats(timeout_seconds=payload.timeout_seconds)
    return {
        "message": f"巡检完成，共将 {len(offline_udids)} 台失联设备标记为 OFFLINE",
        "offline_udids": offline_udids,
    }


@router.delete("/{udid}")
def release_tunnel_endpoint(
    udid: str,
    _user: User = Depends(require_engineer),
) -> Dict[str, Any]:
    """注销并释放指定 iPhone 的反向隧道"""
    released = release_ios_tunnel(udid)
    if not released:
        raise HTTPException(status_code=404, detail="该设备隧道不存在或已被释放")
    return {"message": f"设备 [{udid}] 反向隧道已成功断开释放"}
