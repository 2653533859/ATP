"""多源基础设施容量水位实时度量 REST API (T3.1)。"""

from __future__ import annotations

from typing import Any
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field

from app.api.deps import get_current_user, require_engineer
from app.models.user import User
from app.services.multisource_capacity_watermark_meter import (
    clear_watermark_report_store,
    get_watermark_report,
    list_watermark_reports,
    meter_infrastructure_capacity_watermark,
)

router = APIRouter(prefix="/stress/bottleneck-guardian/watermark", tags=["多源容量水位度量 (T3.1)"])


class MetricSampleIn(BaseModel):
    resource_id: str = Field(..., description="基础设施资源唯一标识 (如 mysql_primary_pool)")
    resource_type: str = Field(
        default="DATABASE_POOL", description="资源类型: DATABASE_POOL, REDIS_CACHE, MESSAGE_QUEUE, HOST_SYSTEM"
    )
    current_value: float = Field(..., description="当前监测值")
    capacity_limit: float = Field(..., description="容量上限阈值")
    unit: str = Field(default="units", description="度量单位 (如 connections, MB, messages, %)")
    detail_metric_name: str | None = Field(default=None, description="细分指标名称")


class MeterWatermarkIn(BaseModel):
    target_cluster_or_env: str = Field(default="prod_east_cluster", description="被测集群或基础设施环境标识")
    metric_samples: list[MetricSampleIn] = Field(..., min_length=1, description="基础设施监控指标采样批次")


@router.post("/meter")
async def meter_watermark_endpoint(
    body: MeterWatermarkIn,
    _user: User = Depends(get_current_user),
) -> dict[str, Any]:
    """采集并聚合多源基础设施监控指标，计算容量水位与健康负荷指数。"""
    _ = _user
    samples_dicts = [s.model_dump() for s in body.metric_samples]
    report = meter_infrastructure_capacity_watermark(
        target_cluster_or_env=body.target_cluster_or_env,
        metric_samples=samples_dicts,
    )
    return {"message": "多源基础设施容量水位度量完成", "report": report.to_dict()}


@router.get("/reports")
async def list_reports_endpoint(
    limit: int = 50,
    _user: User = Depends(get_current_user),
) -> dict[str, Any]:
    """获取历史容量水位评估报告列表。"""
    _ = _user
    reports = list_watermark_reports(limit=limit)
    return {"total": len(reports), "reports": reports}


@router.get("/reports/{report_id}")
async def get_report_endpoint(
    report_id: str,
    _user: User = Depends(get_current_user),
) -> dict[str, Any]:
    """按 ID 查询单次容量水位报告详情。"""
    _ = _user
    report = get_watermark_report(report_id)
    if not report:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"报告 [{report_id}] 不存在")
    return {"report": report.to_dict()}


@router.delete("/reports")
async def clear_reports_endpoint(
    _user: User = Depends(require_engineer),
) -> dict[str, Any]:
    """清空容量水位报告仓库 (需工程师权限)。"""
    _ = _user
    clear_watermark_report_store()
    return {"message": "已清空所有容量水位评估报告"}
