"""OpenTelemetry 全链路 Span 追踪采集中继与树重构 REST API (T1.1)。"""

from __future__ import annotations

from typing import Any
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field

from app.api.deps import get_current_user, require_engineer
from app.models.user import User
from app.services.distributed_trace_telemetry_relay import (
    clear_telemetry_store,
    ingest_spans,
    list_trace_summaries,
    reconstruct_trace_tree,
)

router = APIRouter(prefix="/trace/telemetry", tags=["分布式链路追踪中继与调用树 (T1.1)"])


class IngestSpansIn(BaseModel):
    spans: list[dict[str, Any]] = Field(..., min_length=1, description="OpenTelemetry 标准 Span 字典数组")


@router.post("/spans")
async def ingest_spans_endpoint(
    body: IngestSpansIn,
    _user: User = Depends(get_current_user),
) -> dict[str, Any]:
    """批量上报接收微服务全链路 Span 并执行 Trace 依赖关联。"""
    _ = _user
    res = ingest_spans(body.spans)
    return {"message": "Span 采集中继成功", **res}


@router.get("/traces")
async def list_traces_endpoint(
    limit: int = 50,
    service_name: str | None = None,
    has_error: bool | None = None,
    min_duration_ms: float = 0.0,
    _user: User = Depends(get_current_user),
) -> dict[str, Any]:
    """查询分布式链路汇总列表。"""
    _ = _user
    traces = list_trace_summaries(
        limit=limit,
        service_name=service_name,
        has_error=has_error,
        min_duration_ms=min_duration_ms,
    )
    return {"total": len(traces), "traces": traces}


@router.get("/traces/{trace_id}")
async def get_trace_tree_endpoint(
    trace_id: str,
    _user: User = Depends(get_current_user),
) -> dict[str, Any]:
    """根据 TraceId 重构多层级级联调用树。"""
    _ = _user
    tree = reconstruct_trace_tree(trace_id)
    if not tree:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"链路追踪不存在: {trace_id}",
        )
    return tree.to_dict()


@router.delete("/traces")
async def clear_traces_endpoint(
    _user: User = Depends(require_engineer),
) -> dict[str, Any]:
    """清空链路追踪数据仓库 (需工程师权限)。"""
    _ = _user
    cleared = clear_telemetry_store()
    return {"message": f"已清空 {cleared} 条链路数据", "cleared_count": cleared}
