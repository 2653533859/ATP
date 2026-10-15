"""Device Playback and Automation Lifecycle REST API (T2.1)."""

from __future__ import annotations

from typing import Any
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from app.api.deps import get_current_user, require_engineer
from app.models.user import User
from app.services.device_playback_driver import (
    get_playback_session,
    initialize_playback_session,
    teardown_playback_session,
)

router = APIRouter(prefix="/device-playback", tags=["移动端真机回放与自愈驱动"])


class InitPlaybackSessionIn(BaseModel):
    platform: str = Field(default="android", description="设备平台 (android 或 ios)")
    device_id: int = Field(ge=1, description="平台数据库设备 ID")
    serial_or_udid: str = Field(..., description="Android Serial 或 iOS UDID")
    target_app: str = Field(..., description="目标应用包名或 Bundle ID")


class ExecutePlaybackStepIn(BaseModel):
    step_no: int = Field(default=1, ge=1, description="步骤编号")
    step_dict: dict[str, Any] = Field(..., description="包含 action 和 params 的步骤配置")


@router.post("/sessions/init")
async def init_playback_session_endpoint(
    body: InitPlaybackSessionIn,
    _user: User = Depends(require_engineer),
):
    """初始化并拉起真实 Android 或 iOS 设备的受控回放会话。"""
    try:
        session = await initialize_playback_session(
            platform=body.platform,
            device_id=body.device_id,
            serial_or_udid=body.serial_or_udid,
            target_app=body.target_app,
        )
        return session.get_summary()
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@router.post("/sessions/{session_id}/execute-step")
async def execute_step_endpoint(
    session_id: str,
    body: ExecutePlaybackStepIn,
    _user: User = Depends(require_engineer),
):
    """在当前已连接的真机上受控分发并执行单个回放操作步骤。"""
    session = get_playback_session(session_id)
    if session is None:
        raise HTTPException(status_code=404, detail="回放会话不存在")
    if session.status != "running":
        raise HTTPException(status_code=400, detail=f"会话处于 '{session.status}' 状态，无法执行新步骤")

    record = await session.execute_step(body.step_dict, body.step_no)
    return record.to_dict()


@router.post("/sessions/{session_id}/teardown")
async def teardown_session_endpoint(
    session_id: str,
    _user: User = Depends(require_engineer),
):
    """安全回收真机回放连接并输出执行诊断总览。"""
    summary = await teardown_playback_session(session_id)
    if summary is None:
        raise HTTPException(status_code=404, detail="回放会话不存在")
    return summary


@router.get("/sessions/{session_id}")
async def get_session_endpoint(
    session_id: str,
    _user: User = Depends(get_current_user),
):
    """查询指定真机回放会话的执行步骤与健康状态。"""
    session = get_playback_session(session_id)
    if session is None:
        raise HTTPException(status_code=404, detail="回放会话不存在")
    return session.get_summary()
