"""全链路压测阶梯加压曲线与拐点检测 REST API (T4.1)。"""

from __future__ import annotations

from typing import Any
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field

from app.api.deps import get_current_user, require_engineer
from app.models.user import User
from app.services.step_load_throughput_knee_detector import (
    clear_throughput_knee_store,
    detect_throughput_knee_and_cliff,
    get_throughput_knee_report,
    list_throughput_knee_reports,
)

router = APIRouter(prefix="/stress/drill-report/knee-detection", tags=["压测曲线拐点检测 (T4.1)"])


class StepSampleIn(BaseModel):
    concurrency_threads: int = Field(..., ge=1, description="阶梯并发虚拟用户数 (VU)")
    measured_tps: float = Field(..., ge=0.0, description="实测瞬时吞吐量 TPS")
    avg_latency_ms: float = Field(default=0.0, ge=0.0, description="平均响应时间 ms")
    p99_latency_ms: float = Field(default=0.0, ge=0.0, description="P99 长尾响应时间 ms")
    error_rate_pct: float = Field(default=0.0, ge=0.0, le=100.0, description="错误率百分比")


class AnalyzeKneeIn(BaseModel):
    scenario_name: str = Field(default="step_load_checkout_test", description="阶梯压测场景标识")
    samples: list[StepSampleIn] = Field(..., min_length=2, description="阶梯递增并发加压采样序列")


@router.post("/analyze")
async def analyze_knee_endpoint(
    body: AnalyzeKneeIn,
    _user: User = Depends(get_current_user),
) -> dict[str, Any]:
    """分析阶梯加压采样序列，拟合并发 vs TPS 曲线，精准定位 Knee 性能拐点与 Cliff 崩溃点。"""
    _ = _user
    samples_dicts = [s.model_dump() for s in body.samples]
    report = detect_throughput_knee_and_cliff(
        scenario_name=body.scenario_name,
        samples=samples_dicts,
    )
    return {"message": "阶梯加压性能曲线与拐点分析完成", "report": report.to_dict()}


@router.get("/reports")
async def list_reports_endpoint(
    limit: int = 50,
    _user: User = Depends(get_current_user),
) -> dict[str, Any]:
    """获取历史阶梯加压拐点分析报告列表。"""
    _ = _user
    reports = list_throughput_knee_reports(limit=limit)
    return {"total": len(reports), "reports": reports}


@router.get("/reports/{report_id}")
async def get_report_endpoint(
    report_id: str,
    _user: User = Depends(get_current_user),
) -> dict[str, Any]:
    """按 ID 查询单次阶梯加压拐点分析报告详情。"""
    _ = _user
    report = get_throughput_knee_report(report_id)
    if not report:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"报告 [{report_id}] 不存在")
    return {"report": report.to_dict()}


@router.delete("/reports")
async def clear_reports_endpoint(
    _user: User = Depends(require_engineer),
) -> dict[str, Any]:
    """清空阶梯加压拐点报告仓库 (需工程师权限)。"""
    _ = _user
    clear_throughput_knee_store()
    return {"message": "已清空所有阶梯加压拐点分析报告"}
