"""物理真机集群调度与容量预测 REST API (T1.3)

为多端混合自动化任务提供物理设备集群健康感知、自适应权重调度与容量水位大盘:
1. 真机多维健康遥测上报与列表感知 (/scheduler/telemetry/report, /devices/telemetry);
2. 任务最优物理真机路由派发与配额租约锁定 (/scheduler/route/dispatch);
3. 任务执行完成或失败租约释放 (/scheduler/route/release);
4. 全集群算力与容量预测统计大盘 (/scheduler/capacity/summary);
5. 调度决策流水与详情审计 (/scheduler/routing/history, /scheduler/routing/{decision_id})。
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from app.api.deps import require_engineer
from app.models.user import User
from app.services.fleet_concurrency_router import (
    RoutingStatus,
    TaskExecutionRequirement,
    TaskPriority,
    get_routing_decision,
    list_routing_history,
    release_device_lease,
    route_and_lease_device,
)
from app.services.fleet_health_telemetry import (
    BatteryState,
    DeviceHealthStatus,
    list_fleet_telemetry,
    record_device_telemetry,
)

router = APIRouter(prefix="/scheduler", tags=["Fleet Concurrency Scheduler"])


class ReportTelemetryRequest(BaseModel):
    device_id: str = Field(..., description="物理真机唯一标识 (UDID/Serial)")
    platform: str = Field("ios", description="平台 (ios | android)")
    battery_temperature_c: float = Field(32.0, description="电池温度摄氏度")
    battery_level_percent: int = Field(80, ge=0, le=100, description="电量百分比")
    battery_state: str = Field("CHARGING", description="电池充放电状态")
    cpu_usage_percent: float = Field(20.0, description="CPU 使用率")
    memory_free_mb: int = Field(1500, description="空闲内存")
    current_concurrency: int = Field(0, description="当前承载任务数")
    max_concurrency: int = Field(2, ge=1, le=10, description="最大支持并发上限")
    tunnel_rtt_ms: float = Field(15.0, description="隧道往返时延")


class DispatchTaskRequest(BaseModel):
    task_id: str = Field(..., description="待执行自动化任务 ID")
    target_platform: str = Field("ios", description="目标平台 (ios | android)")
    task_name: Optional[str] = Field("移动自动化任务", description="任务名称")
    preferred_device_id: Optional[str] = Field(None, description="偏好指定设备 ID (可选)")
    min_battery_percent: int = Field(20, ge=5, le=100, description="最低允许电量")
    max_temperature_c: float = Field(42.0, ge=30.0, le=55.0, description="最高允许温度")
    priority: str = Field("NORMAL", description="任务优先级 (CRITICAL | HIGH | NORMAL | LOW)")
    estimated_duration_sec: int = Field(60, ge=5, description="预估耗时秒数")


class ReleaseLeaseRequest(BaseModel):
    device_id: str = Field(..., description="物理真机唯一标识")
    task_id: str = Field(..., description="已完成或释放的任务 ID")


@router.post("/telemetry/report")
def report_telemetry_endpoint(
    payload: ReportTelemetryRequest,
    _user: User = Depends(require_engineer),
) -> Dict[str, Any]:
    """物理真机上报实时环境健康与性能遥测指标"""
    try:
        b_state = BatteryState(payload.battery_state.upper())
    except ValueError:
        b_state = BatteryState.CHARGING

    metric = record_device_telemetry(
        device_id=payload.device_id,
        platform=payload.platform,
        battery_temp_c=payload.battery_temperature_c,
        battery_level=payload.battery_level_percent,
        battery_state=b_state,
        cpu_usage=payload.cpu_usage_percent,
        memory_free_mb=payload.memory_free_mb,
        current_concurrency=payload.current_concurrency,
        max_concurrency=payload.max_concurrency,
        tunnel_rtt_ms=payload.tunnel_rtt_ms,
    )

    return {
        "message": f"设备 [{payload.device_id}] 遥测数据更新成功，健康得分: {metric.health_score} 分 ({metric.health_status.value})",
        "telemetry": metric.to_dict(),
    }


@router.get("/devices/telemetry")
def list_devices_telemetry_endpoint(
    platform: Optional[str] = None,
    _user: User = Depends(require_engineer),
) -> Dict[str, Any]:
    """查询全集群物理真机实时健康指标列表"""
    devices = list_fleet_telemetry(platform=platform)
    return {
        "total": len(devices),
        "devices": [d.to_dict() for d in devices],
    }


@router.post("/route/dispatch")
def dispatch_task_route_endpoint(
    payload: DispatchTaskRequest,
    _user: User = Depends(require_engineer),
) -> Dict[str, Any]:
    """为自动化任务计算自适应多目标最佳执行设备并锁定配额租约"""
    try:
        prio = TaskPriority(payload.priority.upper())
    except ValueError:
        prio = TaskPriority.NORMAL

    req = TaskExecutionRequirement(
        task_id=payload.task_id,
        target_platform=payload.target_platform.lower(),
        task_name=payload.task_name or "移动自动化任务",
        preferred_device_id=payload.preferred_device_id,
        min_battery_percent=payload.min_battery_percent,
        max_temperature_c=payload.max_temperature_c,
        priority=prio,
        estimated_duration_sec=payload.estimated_duration_sec,
    )

    decision = route_and_lease_device(req)
    return {
        "message": f"调度计算完成: {decision.routing_reason}",
        "decision": decision.to_dict(),
        "is_allocated": decision.status == RoutingStatus.ROUTED,
    }


@router.post("/route/release")
def release_lease_endpoint(
    payload: ReleaseLeaseRequest,
    _user: User = Depends(require_engineer),
) -> Dict[str, Any]:
    """任务执行完毕或异常时释放物理真机并发配额租约"""
    success = release_device_lease(payload.device_id, payload.task_id)
    return {
        "message": f"设备 [{payload.device_id}] 配额租约释放 {'成功' if success else '完成 (无活动租约)'}",
        "released": success,
    }


@router.get("/capacity/summary")
def get_capacity_summary_endpoint(
    platform: Optional[str] = None,
    _user: User = Depends(require_engineer),
) -> Dict[str, Any]:
    """查询集群全局算力容量、并发水位与设备健康大盘统计"""
    devices = list_fleet_telemetry(platform=platform)
    total_devices = len(devices)

    healthy_count = sum(1 for d in devices if d.health_status == DeviceHealthStatus.HEALTHY)
    warming_count = sum(1 for d in devices if d.health_status == DeviceHealthStatus.WARMING)
    overheated_count = sum(1 for d in devices if d.health_status == DeviceHealthStatus.OVERHEATED)
    low_bat_count = sum(1 for d in devices if d.health_status == DeviceHealthStatus.LOW_BATTERY)
    offline_count = sum(1 for d in devices if d.health_status == DeviceHealthStatus.OFFLINE)

    total_capacity = sum(d.max_concurrency for d in devices)
    used_concurrency = sum(d.current_concurrency for d in devices)
    available_capacity = max(0, total_capacity - used_concurrency)

    avg_temp = round(sum(d.battery_temperature_c for d in devices) / total_devices, 1) if total_devices > 0 else 0.0
    avg_bat = round(sum(d.battery_level_percent for d in devices) / total_devices, 1) if total_devices > 0 else 0.0
    avg_rtt = round(sum(d.tunnel_rtt_ms for d in devices) / total_devices, 1) if total_devices > 0 else 0.0

    return {
        "total_devices": total_devices,
        "healthy_count": healthy_count,
        "warming_count": warming_count,
        "overheated_count": overheated_count,
        "low_battery_count": low_bat_count,
        "offline_count": offline_count,
        "total_capacity": total_capacity,
        "used_concurrency": used_concurrency,
        "available_capacity": available_capacity,
        "cluster_averages": {
            "avg_temperature_c": avg_temp,
            "avg_battery_percent": avg_bat,
            "avg_tunnel_rtt_ms": avg_rtt,
        },
    }


@router.get("/routing/history")
def list_routing_history_endpoint(
    limit: int = 50,
    _user: User = Depends(require_engineer),
) -> Dict[str, Any]:
    """查询近期调度决策历史流水"""
    history = list_routing_history(limit=limit)
    return {
        "total": len(history),
        "history": history,
    }


@router.get("/routing/{decision_id}")
def get_routing_decision_endpoint(
    decision_id: str,
    _user: User = Depends(require_engineer),
) -> Dict[str, Any]:
    """查询单次调度决策详情"""
    record = get_routing_decision(decision_id)
    if not record:
        raise HTTPException(status_code=404, detail="未找到目标调度决策记录")
    return {"decision": record.to_dict()}
