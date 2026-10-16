"""压测调用链热点慢调用与资源争用瓶颈归因 REST API (T3.2)。"""

from __future__ import annotations

from typing import Any
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field

from app.api.deps import get_current_user, require_engineer
from app.models.user import User
from app.services.distributed_bottleneck_root_cause_classifier import (
    classify_distributed_bottlenecks,
    clear_bottleneck_report_store,
    get_bottleneck_report,
    list_bottleneck_reports,
)

router = APIRouter(prefix="/stress/bottleneck-guardian/bottlenecks", tags=["下游热点瓶颈归因 (T3.2)"])


class SpanMetricIn(BaseModel):
    span_id: str | None = Field(default=None, description="调用链 Span ID")
    service_name: str = Field(..., description="微服务名称")
    endpoint_or_sql: str | None = Field(default=None, description="接口路径或 SQL 语句")
    duration_ms: float = Field(..., description="调用执行耗时 ms")
    error_message: str | None = Field(default=None, description="错误日志或异常堆栈信息")
    lock_wait_time_ms: float = Field(default=0.0, description="行锁或事务锁等待时间 ms")
    thread_queue_depth: int = Field(default=0, description="当前线程池排队等待队列深度")
    cpu_usage_pct: float = Field(default=0.0, description="节点 CPU 占用百分比")


class ClassifyBottlenecksIn(BaseModel):
    scenario_name: str = Field(default="stress_checkout_flow", description="压测场景或流水线标识")
    spans: list[SpanMetricIn] = Field(..., min_length=1, description="调用链 Span 执行指标样本集")


@router.post("/classify")
async def classify_bottlenecks_endpoint(
    body: ClassifyBottlenecksIn,
    _user: User = Depends(get_current_user),
) -> dict[str, Any]:
    """深度分析调用链 Span 样本集，量化 P99 延迟，自动归因慢调用、锁争用与线程池瓶颈。"""
    _ = _user
    spans_dicts = [s.model_dump() for s in body.spans]
    report = classify_distributed_bottlenecks(
        scenario_name=body.scenario_name,
        spans=spans_dicts,
    )
    return {"message": "调用链瓶颈智能归因分析完成", "report": report.to_dict()}


@router.get("/reports")
async def list_reports_endpoint(
    limit: int = 50,
    _user: User = Depends(get_current_user),
) -> dict[str, Any]:
    """获取历史瓶颈归因报告列表。"""
    _ = _user
    reports = list_bottleneck_reports(limit=limit)
    return {"total": len(reports), "reports": reports}


@router.get("/reports/{report_id}")
async def get_report_endpoint(
    report_id: str,
    _user: User = Depends(get_current_user),
) -> dict[str, Any]:
    """按 ID 查询单次瓶颈归因报告详情。"""
    _ = _user
    report = get_bottleneck_report(report_id)
    if not report:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"报告 [{report_id}] 不存在")
    return {"report": report.to_dict()}


@router.delete("/reports")
async def clear_reports_endpoint(
    _user: User = Depends(require_engineer),
) -> dict[str, Any]:
    """清空瓶颈归因报告仓库 (需工程师权限)。"""
    _ = _user
    clear_bottleneck_report_store()
    return {"message": "已清空所有瓶颈归因审计报告"}
