"""核心体验 Web Vitals 全景审计报告 REST API (T4.3)。"""

from __future__ import annotations

from typing import Any
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field

from app.api.deps import get_current_user, require_engineer
from app.models.user import User
from app.services.web_vitals_experience_audit_reporter import (
    clear_web_vitals_store,
    generate_web_vitals_report,
    get_web_vitals_report,
    list_web_vitals_reports,
)

router = APIRouter(prefix="/client-perf/web-vitals-report", tags=["Web Vitals 体验审计报告 (T4.3)"])


class GenerateWebVitalsIn(BaseModel):
    target_url_or_page: str = Field(default="https://atp.example.com/workbench", description="页面 URL 或名称")
    lcp_ms: float = Field(..., description="Largest Contentful Paint 耗时 ms")
    inp_ms: float = Field(..., description="Interaction to Next Paint 延迟 ms")
    cls_score: float = Field(..., description="Cumulative Layout Shift 累计布局位移分数")
    fcp_ms: float | None = Field(default=None, description="First Contentful Paint 耗时 ms")
    ttfb_ms: float | None = Field(default=None, description="Time to First Byte 耗时 ms")


@router.post("/generate")
async def generate_web_vitals_endpoint(
    body: GenerateWebVitalsIn,
    _user: User = Depends(get_current_user),
) -> dict[str, Any]:
    """汇总量化 Web Vitals (LCP/INP/CLS) 核心指标，生成全景体验报告与优化建议。"""
    _ = _user
    report = generate_web_vitals_report(
        target_url_or_page=body.target_url_or_page,
        lcp_ms=body.lcp_ms,
        inp_ms=body.inp_ms,
        cls_score=body.cls_score,
        fcp_ms=body.fcp_ms,
        ttfb_ms=body.ttfb_ms,
    )
    return {"message": "Web Vitals 核心体验审计报告已生成", "report": report.to_dict()}


@router.get("/reports")
async def list_reports_endpoint(
    limit: int = 50,
    _user: User = Depends(get_current_user),
) -> dict[str, Any]:
    """获取历史 Web Vitals 报告列表。"""
    _ = _user
    reports = list_web_vitals_reports(limit=limit)
    return {"total": len(reports), "reports": reports}


@router.get("/reports/{report_id}")
async def get_report_endpoint(
    report_id: str,
    _user: User = Depends(get_current_user),
) -> dict[str, Any]:
    """按 ID 查询单次 Web Vitals 报告详情。"""
    _ = _user
    report = get_web_vitals_report(report_id)
    if not report:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"报告 [{report_id}] 不存在")
    return {"report": report.to_dict()}


@router.get("/reports/{report_id}/markdown")
async def get_report_markdown_endpoint(
    report_id: str,
    _user: User = Depends(get_current_user),
) -> dict[str, Any]:
    """导出结构化 Markdown 格式报告。"""
    _ = _user
    report = get_web_vitals_report(report_id)
    if not report:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"报告 [{report_id}] 不存在")
    return {"report_id": report.report_id, "markdown": report.to_markdown()}


@router.delete("/reports")
async def clear_reports_endpoint(
    _user: User = Depends(require_engineer),
) -> dict[str, Any]:
    """清空 Web Vitals 报告仓库 (需工程师权限)。"""
    _ = _user
    clear_web_vitals_store()
    return {"message": "已清空所有 Web Vitals 审计报告"}
