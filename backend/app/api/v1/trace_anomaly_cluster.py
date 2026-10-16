"""分布式调用链路慢调用智能聚类诊断 REST API (T1.3)。"""

from __future__ import annotations

from typing import Any
from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field

from app.api.deps import get_current_user
from app.models.user import User
from app.services.trace_anomaly_slow_call_clusterer import (
    cluster_trace_anomalies,
    diagnose_telemetry_traces,
)

router = APIRouter(prefix="/trace/anomaly-cluster", tags=["慢调用聚类与异常波动诊断 (T1.3)"])


class AnalyzeAnomalyIn(BaseModel):
    spans: list[dict[str, Any]] = Field(..., min_length=1, description="待分析的 Span 列表")
    slow_threshold_ms: float = Field(default=200.0, ge=1.0, description="慢调用判定阈值 (毫秒)")


@router.post("/analyze")
async def analyze_anomalies_endpoint(
    body: AnalyzeAnomalyIn,
    _user: User = Depends(get_current_user),
) -> dict[str, Any]:
    """对传入的 Span 集合执行慢调用模式聚类与时延偏离度量。"""
    _ = _user
    report = cluster_trace_anomalies(
        spans=body.spans,
        slow_threshold_ms=body.slow_threshold_ms,
    )
    return report.to_dict()


@router.get("/telemetry")
async def diagnose_telemetry_endpoint(
    slow_threshold_ms: float = 200.0,
    _user: User = Depends(get_current_user),
) -> dict[str, Any]:
    """直接对中继数据仓库中的全网分布式 Trace 执行慢调用聚类诊断。"""
    _ = _user
    report = diagnose_telemetry_traces(slow_threshold_ms=slow_threshold_ms)
    return report.to_dict()
