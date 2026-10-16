"""分布式追踪 TraceID 贯通与慢调用火焰图分析 API (D3.3)."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field

from app.api.deps import get_current_user, require_engineer
from app.models.user import User
from app.services.distributed_trace_flamegraph import (
    build_trace_flamegraph,
    get_trace_report,
    list_traces,
)

router = APIRouter(prefix="/diagnostics/traces", tags=["分布式追踪与慢调用火焰图"])


class IngestTraceSpansIn(BaseModel):
    trace_id: str = Field(min_length=2, max_length=128, description="分布式追踪全局唯一 TraceID")
    spans: list[dict[str, Any]] = Field(
        min_length=1, description="全链路采集到的 OpenTelemetry / Jaeger 标准 Spans 列表"
    )
    slow_span_threshold_ms: float = Field(default=100.0, ge=1.0, description="判定慢调用阈值 (毫秒)")


@router.post("/ingest")
async def ingest_trace_spans_endpoint(
    body: IngestTraceSpansIn,
    _user: User = Depends(require_engineer),
) -> dict[str, Any]:
    """摄入全链路分布式 Spans 调用数据，构建调用拓扑树并生成标准火焰图 (需工程师权限)。"""
    _ = _user
    try:
        report = build_trace_flamegraph(
            trace_id=body.trace_id,
            raw_spans=body.spans,
            slow_span_threshold_ms=body.slow_span_threshold_ms,
        )
        return {"message": "全链路 Trace 火焰图构建成功", "report": report.to_dict()}
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))


@router.get("")
async def list_traces_endpoint(
    service_name: str | None = Query(default=None, description="按参与的微服务名过滤"),
    _user: User = Depends(get_current_user),
) -> dict[str, Any]:
    """查询当前已摄入的全部全链路追踪报告列表。"""
    _ = _user
    traces = list_traces()
    if service_name:
        traces = [t for t in traces if service_name in t.services_involved]
    return {"total": len(traces), "traces": [t.to_dict() for t in traces]}


@router.get("/{trace_id}")
async def get_trace_report_endpoint(
    trace_id: str,
    _user: User = Depends(get_current_user),
) -> dict[str, Any]:
    """获取指定 TraceID 的火焰图树形结构、独占耗时与慢调用分析详情。"""
    _ = _user
    report = get_trace_report(trace_id)
    if not report:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Trace 报告不存在: {trace_id}")
    return report.to_dict()
