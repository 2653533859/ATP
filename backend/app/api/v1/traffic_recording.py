"""Traffic Recording and Proxy Gateway REST API (T1.1)."""

from __future__ import annotations

from typing import Any
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from app.api.deps import get_current_user
from app.models.user import User
from app.services.traffic_recorder_gateway import (
    get_recording_session,
    start_recording_session,
    stop_recording_session,
)

router = APIRouter(prefix="/traffic-recording", tags=["全协议流量录制与用例逆向生成"])


class StartRecordingIn(BaseModel):
    project_id: int = Field(ge=1, description="关联项目 ID")
    target_base_url: str = Field(..., description="目标服务 Base URL (如 http://192.168.1.10:8080)")
    filter_noise: bool = Field(default=True, description="是否自动滤除静态资源与心跳请求")


class RecordTrafficEntryIn(BaseModel):
    method: str = Field(default="GET", description="HTTP 方法")
    path: str = Field(..., description="请求路径 (如 /api/v1/orders/123)")
    headers: dict[str, str] = Field(default_factory=dict, description="请求头")
    query_params: dict[str, str] = Field(default_factory=dict, description="Query 参数")
    request_body: Any = Field(default=None, description="请求 Body")
    status_code: int = Field(default=200, description="响应状态码")
    response_headers: dict[str, str] = Field(default_factory=dict, description="响应头")
    response_body: Any = Field(default=None, description="响应 Body")
    duration_ms: float = Field(default=50.0, ge=0.0, description="接口执行耗时(毫秒)")


@router.post("/sessions/start")
async def start_session_endpoint(
    body: StartRecordingIn,
    _user: User = Depends(get_current_user),
):
    """启动反向代理流量录制会话。"""
    try:
        session = start_recording_session(
            project_id=body.project_id,
            target_base_url=body.target_base_url,
            filter_noise=body.filter_noise,
        )
        return session.get_summary()
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@router.post("/sessions/{session_id}/stop")
async def stop_session_endpoint(
    session_id: str,
    _user: User = Depends(get_current_user),
):
    """终止指定的流量录制会话并输出清洗汇总。"""
    summary = stop_recording_session(session_id)
    if summary is None:
        raise HTTPException(status_code=404, detail="录制会话不存在")
    return summary


@router.get("/sessions/{session_id}")
async def get_session_endpoint(
    session_id: str,
    _user: User = Depends(get_current_user),
):
    """获取指定录制会话的当前状态与捕获的清洗流量。"""
    session = get_recording_session(session_id)
    if session is None:
        raise HTTPException(status_code=404, detail="录制会话不存在")
    return session.get_summary()


@router.post("/sessions/{session_id}/record")
async def record_entry_endpoint(
    session_id: str,
    body: RecordTrafficEntryIn,
    _user: User = Depends(get_current_user),
):
    """手动或网关代理拦截并写入单条流量抓包请求/响应。"""
    session = get_recording_session(session_id)
    if session is None:
        raise HTTPException(status_code=404, detail="录制会话不存在")
    if session.status != "active":
        raise HTTPException(status_code=400, detail="录制会话已停止，无法写入新流量")

    entry = session.record_entry(
        method=body.method,
        path=body.path,
        headers=body.headers,
        query_params=body.query_params,
        request_body=body.request_body,
        status_code=body.status_code,
        response_headers=body.response_headers,
        response_body=body.response_body,
        duration_ms=body.duration_ms,
    )
    return entry.to_dict()
