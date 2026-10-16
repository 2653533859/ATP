"""全生命周期多维质量健康综合评分 REST API (T4.1)。"""

from __future__ import annotations

from typing import Any
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field

from app.api.deps import get_current_user, require_engineer
from app.models.user import User
from app.services.quality_health_composite_score_engine import (
    QualityInputMetrics,
    calculate_quality_health_score,
    clear_health_score_store,
    get_quality_health_report,
    list_quality_health_reports,
)

router = APIRouter(prefix="/gatekeeper/health-score", tags=["质量健康综合评分 (T4.1)"])


class CalculateHealthScoreIn(BaseModel):
    target_name: str = Field(default="release-v4.2.0", description="评估目标名称或版本号")
    test_pass_rate_pct: float = Field(default=100.0, ge=0.0, le=100.0, description="用例通过率 (%)")
    code_coverage_pct: float = Field(default=85.0, ge=0.0, le=100.0, description="核心代码覆盖率 (%)")
    mutation_score_pct: float = Field(default=80.0, ge=0.0, le=100.0, description="变异测试得分 (%)")
    p0_defects_count: int = Field(default=0, ge=0, description="P0 缺陷数")
    p1_defects_count: int = Field(default=0, ge=0, description="P1 缺陷数")
    p2_defects_count: int = Field(default=0, ge=0, description="P2 缺陷数")
    change_risk_score: float = Field(default=10.0, ge=0.0, le=100.0, description="变更风险指数 (0~100)")
    compliance_score_pct: float = Field(default=100.0, ge=0.0, le=100.0, description="合规健康度 (%)")


@router.post("/calculate")
async def calculate_health_score_endpoint(
    body: CalculateHealthScoreIn,
    _user: User = Depends(get_current_user),
) -> dict[str, Any]:
    """融合多维指标计算质量健康得分与系统评级。"""
    _ = _user
    metrics = QualityInputMetrics(
        test_pass_rate_pct=body.test_pass_rate_pct,
        code_coverage_pct=body.code_coverage_pct,
        mutation_score_pct=body.mutation_score_pct,
        p0_defects_count=body.p0_defects_count,
        p1_defects_count=body.p1_defects_count,
        p2_defects_count=body.p2_defects_count,
        change_risk_score=body.change_risk_score,
        compliance_score_pct=body.compliance_score_pct,
    )
    result = calculate_quality_health_score(target_name=body.target_name, metrics=metrics)
    return {"message": "多维质量健康综合评分计算完成", "report": result.to_dict()}


@router.get("/reports")
async def list_reports_endpoint(
    limit: int = 50,
    _user: User = Depends(get_current_user),
) -> dict[str, Any]:
    """获取历史质量健康评分报告列表。"""
    _ = _user
    reports = list_quality_health_reports(limit=limit)
    return {"total": len(reports), "reports": reports}


@router.get("/reports/{report_id}")
async def get_report_endpoint(
    report_id: str,
    _user: User = Depends(get_current_user),
) -> dict[str, Any]:
    """查询单次健康评分详情。"""
    _ = _user
    report = get_quality_health_report(report_id)
    if not report:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"报告 [{report_id}] 不存在")
    return {"report": report.to_dict()}


@router.delete("/reports")
async def clear_reports_endpoint(
    _user: User = Depends(require_engineer),
) -> dict[str, Any]:
    """清空健康评分报告（需工程师权限）。"""
    _ = _user
    clear_health_score_store()
    return {"message": "已清空所有质量健康评分记录"}
