"""移动端性能多维时序采样与卡顿泄露诊断 API (D3.1)."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field

from app.api.deps import get_current_user, require_engineer
from app.models.user import User
from app.services.mobile_perf_profiler import (
    MobilePerfSessionConfig,
    PerformanceSamplePoint,
    get_perf_session_report,
    list_perf_sessions,
    record_perf_samples_batch,
    start_perf_session,
    stop_perf_session,
)

router = APIRouter(prefix="/diagnostics/mobile-perf", tags=["移动端原生性能多维诊断"])


class StartPerfSessionIn(BaseModel):
    session_id: str = Field(min_length=2, max_length=64, description="性能采集会话 ID")
    device_serial: str = Field(min_length=1, max_length=128, description="目标移动设备序列号")
    package_name: str = Field(min_length=1, max_length=128, description="目标被测 App 包名")
    sample_interval_sec: float = Field(default=1.0, ge=0.1, le=10.0, description="采样间隔 (秒)")


class SamplePointIn(BaseModel):
    timestamp_sec: float = Field(description="采样时间戳 (秒)")
    cpu_app_pct: float = Field(default=0.0, ge=0.0, le=100.0, description="App CPU 占用率")
    cpu_total_pct: float = Field(default=0.0, ge=0.0, le=100.0, description="系统总 CPU 占用率")
    memory_pss_mb: float = Field(default=0.0, ge=0.0, description="物理内存 PSS (MB)")
    memory_native_heap_mb: float = Field(default=0.0, ge=0.0, description="Native Heap (MB)")
    memory_dalvik_heap_mb: float = Field(default=0.0, ge=0.0, description="Dalvik Heap (MB)")
    fps: float = Field(default=60.0, ge=0.0, le=144.0, description="渲染帧率 FPS")
    jank_count: int = Field(default=0, ge=0, description="卡顿掉帧数")
    net_tx_kbps: float = Field(default=0.0, ge=0.0, description="上行速率 (KB/s)")
    net_rx_kbps: float = Field(default=0.0, ge=0.0, description="下行速率 (KB/s)")


class BatchAppendSamplesIn(BaseModel):
    samples: list[SamplePointIn] = Field(min_length=1, description="时序采样点数据集合")


@router.post("/sessions/start")
async def start_perf_session_endpoint(
    body: StartPerfSessionIn,
    _user: User = Depends(require_engineer),
) -> dict[str, Any]:
    """启动移动端设备应用性能采集会话 (需工程师权限)。"""
    _ = _user
    config = MobilePerfSessionConfig(
        session_id=body.session_id,
        device_serial=body.device_serial,
        package_name=body.package_name,
        sample_interval_sec=body.sample_interval_sec,
    )
    session = start_perf_session(config)
    return {"message": "性能采集会话已成功启动", "session": session.to_dict()}


@router.post("/sessions/{session_id}/samples")
async def append_perf_samples_endpoint(
    session_id: str,
    body: BatchAppendSamplesIn,
    _user: User = Depends(require_engineer),
) -> dict[str, Any]:
    """向指定会话批量追加设备上报的时序性能指标数据。"""
    _ = _user
    points = [
        PerformanceSamplePoint(
            timestamp_sec=s.timestamp_sec,
            cpu_app_pct=s.cpu_app_pct,
            cpu_total_pct=s.cpu_total_pct,
            memory_pss_mb=s.memory_pss_mb,
            memory_native_heap_mb=s.memory_native_heap_mb,
            memory_dalvik_heap_mb=s.memory_dalvik_heap_mb,
            fps=s.fps,
            jank_count=s.jank_count,
            net_tx_kbps=s.net_tx_kbps,
            net_rx_kbps=s.net_rx_kbps,
        )
        for s in body.samples
    ]
    try:
        record_perf_samples_batch(session_id, points)
        return {"message": f"成功追加 {len(points)} 个性能采样点", "session_id": session_id}
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))


@router.post("/sessions/{session_id}/stop")
async def stop_perf_session_endpoint(
    session_id: str,
    _user: User = Depends(require_engineer),
) -> dict[str, Any]:
    """停止采样会话，执行深度诊断分析并输出性能体检报告与异常列表。"""
    _ = _user
    try:
        report = stop_perf_session(session_id)
        return {"message": "性能诊断报告已生成", "report": report.to_dict()}
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))


@router.get("/sessions")
async def list_perf_sessions_endpoint(
    _user: User = Depends(get_current_user),
) -> dict[str, Any]:
    """查询全部已记录的移动端性能诊断会话列表。"""
    _ = _user
    sessions = list_perf_sessions()
    return {"total": len(sessions), "sessions": [s.to_dict() for s in sessions]}


@router.get("/sessions/{session_id}")
async def get_perf_session_endpoint(
    session_id: str,
    _user: User = Depends(get_current_user),
) -> dict[str, Any]:
    """获取单个性能诊断会话的完整报告与指标明细。"""
    _ = _user
    report = get_perf_session_report(session_id)
    if not report:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"性能会话不存在: {session_id}")
    return report.to_dict()
