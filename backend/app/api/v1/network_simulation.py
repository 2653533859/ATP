"""Network Simulation and Throttling REST API (Q1.1)."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from app.api.deps import get_current_user
from app.models.user import User
from app.services.network_simulation import (
    calculate_network_transmission_delay,
    generate_adb_network_commands,
    generate_cdp_network_conditions,
    get_preset_network_profiles,
    is_packet_dropped,
)

router = APIRouter(prefix="/network-profiles", tags=["网络仿真与弱网治理"])


class NetworkSimulateEvaluateIn(BaseModel):
    profile_id: str = "2g_edge"
    payload_bytes: int = Field(default=1024, ge=0)
    custom_profile: dict[str, Any] | None = None


class NetworkSimulateEvaluateOut(BaseModel):
    profile_id: str
    is_dropped: bool
    estimated_delay_seconds: float
    offline: bool
    cdp_conditions: dict[str, Any]
    adb_commands: list[list[str]]


@router.get("")
async def list_network_profiles_endpoint(
    _user: User = Depends(get_current_user),
) -> dict[str, Any]:
    """获取系统预设的标准弱网仿真配置档案（2G/3G/4G/离线/高丢包等）。"""
    return get_preset_network_profiles()


@router.post("/evaluate", response_model=NetworkSimulateEvaluateOut)
async def evaluate_network_profile_endpoint(
    body: NetworkSimulateEvaluateIn,
    _user: User = Depends(get_current_user),
):
    """根据给定的数据包大小与弱网档案，评估预期传输延迟、丢包判定与底层设备配置指令。"""
    presets = get_preset_network_profiles()
    profile = body.custom_profile or presets.get(body.profile_id)
    if not profile:
        raise HTTPException(status_code=404, detail=f"未找到网络仿真档案: {body.profile_id}")

    dropped = is_packet_dropped(profile)
    delay_s = calculate_network_transmission_delay(profile, body.payload_bytes)
    cdp = generate_cdp_network_conditions(profile)
    adb = generate_adb_network_commands(profile)

    return NetworkSimulateEvaluateOut(
        profile_id=body.profile_id,
        is_dropped=dropped,
        estimated_delay_seconds=delay_s,
        offline=bool(profile.get("offline", False)),
        cdp_conditions=cdp,
        adb_commands=adb,
    )
