"""跨服务关键路径分析与火焰图定位 REST API (T1.2)。"""

from __future__ import annotations

from typing import Any
import uuid
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field

from app.api.deps import get_current_user
from app.models.user import User
from app.services.critical_path_flamegraph_profiler import (
    profile_spans_critical_path,
    profile_trace_critical_path_by_id,
)

router = APIRouter(prefix="/trace/flamegraph", tags=["关键路径与火焰图性能瓶颈 (T1.2)"])


class ProfileSpansIn(BaseModel):
    trace_id: str | None = Field(default=None, description="链路 TraceId (选填，留空自动生成)")
    spans: list[dict[str, Any]] = Field(..., min_length=1, description="待分析的 Span 字典数组")


@router.get("/profile/{trace_id}")
async def profile_trace_endpoint(
    trace_id: str,
    _user: User = Depends(get_current_user),
) -> dict[str, Any]:
    """根据 TraceId 推导链路关键路径、耗时贡献度占比与火焰图树形结构。"""
    _ = _user
    report = profile_trace_critical_path_by_id(trace_id)
    if not report:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"未找到该链路追踪数据: {trace_id}",
        )
    return report.to_dict()


@router.post("/profile-spans")
async def profile_spans_endpoint(
    body: ProfileSpansIn,
    _user: User = Depends(get_current_user),
) -> dict[str, Any]:
    """传入自定义 Span 集合实时推导关键路径、定位瓶颈类型并返回火焰图结构。"""
    _ = _user
    tid = body.trace_id or uuid.uuid4().hex
    report = profile_spans_critical_path(trace_id=tid, spans=body.spans)
    return report.to_dict()
