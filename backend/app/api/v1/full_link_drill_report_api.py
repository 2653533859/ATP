"""全链路压力演练综合审计报告 REST API (T4.3)。"""

from __future__ import annotations

from typing import Any
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field

from app.api.deps import get_current_user, require_engineer
from app.models.user import User
from app.services.full_link_stress_drill_reporter import (
    clear_full_drill_report_store,
    generate_full_link_stress_drill_report,
    get_full_drill_report,
    list_full_drill_reports,
)

router = APIRouter(prefix="/stress/drill-report/summary", tags=["全链路压测复盘报告 (T4.3)"])


class GenerateDrillReportIn(BaseModel):
    drill_id: str = Field(default="drill_black_friday_final", description="压测演练计划单号")
    scenario_name: str = Field(default="电商核心全链路加压演练", description="压测场景名称")
    peak_concurrency_vu: int = Field(..., ge=1, description="实测峰值并发虚拟用户数 (VU)")
    peak_tps: float = Field(..., ge=0.0, description="实测峰值系统吞吐量 (TPS)")
    p99_latency_ms: float = Field(..., ge=0.0, description="P99 长尾响应时间 ms")
    error_rate_pct: float = Field(..., ge=0.0, le=100.0, description="系统请求错误率百分比")
    knee_point_concurrency: int = Field(..., ge=1, description="Knee 拐点并发数")
    knee_point_tps: float = Field(..., ge=0.0, description="Knee 拐点吞吐量 TPS")
    cliff_point_concurrency: int | None = Field(default=None, description="Cliff 崩溃点并发数")
    max_db_watermark_pct: float = Field(default=65.0, ge=0.0, le=100.0, description="数据库连接池最高水位")
    max_redis_watermark_pct: float = Field(default=55.0, ge=0.0, le=100.0, description="Redis 内存最高水位")
    max_mq_backlog: int = Field(default=1200, ge=0, description="消息队列峰值积压数")
    circuit_breaker_triggered: bool = Field(default=False, description="是否触发了防雪崩硬核熔断")
    failover_rto_ms: float = Field(default=1450.0, ge=0.0, description="单元容灾 RTO 接管耗时 ms")


@router.post("/generate")
async def generate_report_endpoint(
    body: GenerateDrillReportIn,
    _user: User = Depends(get_current_user),
) -> dict[str, Any]:
    """汇总量化全链路压测各维度指标，进行综合评级并生成带 SHA-256 防篡改签名的复盘报告。"""
    _ = _user
    report = generate_full_link_stress_drill_report(
        drill_id=body.drill_id,
        scenario_name=body.scenario_name,
        peak_concurrency_vu=body.peak_concurrency_vu,
        peak_tps=body.peak_tps,
        p99_latency_ms=body.p99_latency_ms,
        error_rate_pct=body.error_rate_pct,
        knee_point_concurrency=body.knee_point_concurrency,
        knee_point_tps=body.knee_point_tps,
        cliff_point_concurrency=body.cliff_point_concurrency,
        max_db_watermark_pct=body.max_db_watermark_pct,
        max_redis_watermark_pct=body.max_redis_watermark_pct,
        max_mq_backlog=body.max_mq_backlog,
        circuit_breaker_triggered=body.circuit_breaker_triggered,
        failover_rto_ms=body.failover_rto_ms,
    )
    return {"message": "全链路压力演练综合审计报告已生成", "report": report.to_dict()}


@router.get("/reports")
async def list_reports_endpoint(
    limit: int = 50,
    _user: User = Depends(get_current_user),
) -> dict[str, Any]:
    """获取历史全链路压测复盘报告列表。"""
    _ = _user
    reports = list_full_drill_reports(limit=limit)
    return {"total": len(reports), "reports": reports}


@router.get("/reports/{report_id}")
async def get_report_endpoint(
    report_id: str,
    _user: User = Depends(get_current_user),
) -> dict[str, Any]:
    """按 ID 查询单次压测复盘报告详情。"""
    _ = _user
    report = get_full_drill_report(report_id)
    if not report:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"报告 [{report_id}] 不存在")
    return {"report": report.to_dict()}


@router.get("/reports/{report_id}/markdown")
async def get_report_markdown_endpoint(
    report_id: str,
    _user: User = Depends(get_current_user),
) -> dict[str, Any]:
    """导出结构化标准 Markdown 格式报告。"""
    _ = _user
    report = get_full_drill_report(report_id)
    if not report:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"报告 [{report_id}] 不存在")
    return {"report_id": report.report_id, "markdown": report.to_markdown()}


@router.delete("/reports")
async def clear_reports_endpoint(
    _user: User = Depends(require_engineer),
) -> dict[str, Any]:
    """清空全链路压测复盘报告仓库 (需工程师权限)。"""
    _ = _user
    clear_full_drill_report_store()
    return {"message": "已清空所有全链路压测复盘报告"}
