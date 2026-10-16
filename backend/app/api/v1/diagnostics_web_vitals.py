"""Web 性能 Core Web Vitals 自动化深度诊断 API (D3.2)."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field

from app.api.deps import get_current_user, require_engineer
from app.models.user import User
from app.services.web_vitals_profiler import (
    diagnose_web_vitals,
    get_web_vitals_report,
    list_web_vitals_reports,
)

router = APIRouter(prefix="/diagnostics/web-vitals", tags=["Web 性能 Core Web Vitals 自动化深度诊断"])


class DiagnoseWebVitalsIn(BaseModel):
    target_url: str = Field(min_length=3, max_length=512, description="被诊断的目标 Web 页面 URL")
    lcp_ms: float = Field(default=2200.0, ge=0.0, description="最大内容渲染时间 LCP (ms)")
    inp_ms: float = Field(default=120.0, ge=0.0, description="交互到下次绘制延迟 INP (ms)")
    cls_score: float = Field(default=0.05, ge=0.0, description="累积布局偏移 CLS 分数")
    fcp_ms: float = Field(default=1400.0, ge=0.0, description="首次内容渲染时间 FCP (ms)")
    ttfb_ms: float = Field(default=350.0, ge=0.0, description="首字节响应时间 TTFB (ms)")
    tbt_ms: float = Field(default=150.0, ge=0.0, description="总阻塞时间 TBT (ms)")
    raw_resources: list[dict[str, Any]] | None = Field(default=None, description="页面捕获的关键静态资源加载瀑布流水")
    browser_type: str = Field(default="chromium", description="浏览器内核 (chromium | firefox | webkit)")
    device_emulation: str = Field(default="desktop", description="设备模式 (desktop | mobile)")


@router.post("/diagnose")
async def diagnose_web_vitals_endpoint(
    body: DiagnoseWebVitalsIn,
    _user: User = Depends(require_engineer),
) -> dict[str, Any]:
    """对目标 Web 页面执行 Core Web Vitals 多维深度诊断并生成优化建议 (需工程师权限)。"""
    _ = _user
    report = diagnose_web_vitals(
        target_url=body.target_url,
        lcp_ms=body.lcp_ms,
        inp_ms=body.inp_ms,
        cls_score=body.cls_score,
        fcp_ms=body.fcp_ms,
        ttfb_ms=body.ttfb_ms,
        tbt_ms=body.tbt_ms,
        raw_resources=body.raw_resources,
        browser_type=body.browser_type,
        device_emulation=body.device_emulation,
    )
    return {"message": "Web Vitals 性能诊断完成", "report": report.to_dict()}


@router.get("/reports")
async def list_web_vitals_reports_endpoint(
    _user: User = Depends(get_current_user),
) -> dict[str, Any]:
    """查询历史 Web Vitals 诊断报告列表。"""
    _ = _user
    reports = list_web_vitals_reports()
    return {"total": len(reports), "reports": [r.to_dict() for r in reports]}


@router.get("/reports/{audit_id}")
async def get_web_vitals_report_endpoint(
    audit_id: str,
    _user: User = Depends(get_current_user),
) -> dict[str, Any]:
    """获取指定 Web Vitals 性能报告详情与阻断建议。"""
    _ = _user
    report = get_web_vitals_report(audit_id)
    if not report:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"诊断报告不存在: {audit_id}")
    return report.to_dict()
