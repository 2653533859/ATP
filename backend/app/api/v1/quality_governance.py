"""Software Quality Governance & Multi-Dimensional Health Metrics REST API Router (C4.1)."""

from __future__ import annotations

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field

from app.api.deps import get_current_user
from app.models.user import User
from app.services.quality_metrics_engine import compute_quality_health_report

router = APIRouter(prefix="/quality", tags=["企业级测试质量度量与门禁中心"])


class EvaluateQualityMetricsIn(BaseModel):
    project_id: int = Field(ge=1, description="项目 ID")
    total_cases: int = Field(default=100, ge=1, description="测试用例总数")
    automated_cases: int = Field(default=85, ge=0, description="已实现自动化用例数")
    internal_defects: int = Field(default=40, ge=0, description="测试阶段发现的内部缺陷数")
    prod_escapes: int = Field(default=2, ge=0, description="线上逃逸生产缺陷数")
    total_runs: int = Field(default=50, ge=1, description="近期评估的测试执行总轮次")
    flaky_runs: int = Field(default=2, ge=0, description="包含波动或 Flaky 结果的执行轮次")
    mttr_hours: float = Field(default=3.5, ge=0.1, description="平均缺陷修复用时 (小时)")


@router.get("/metrics/project/{project_id}")
async def get_project_quality_metrics_endpoint(
    project_id: int,
    _user: User = Depends(get_current_user),
):
    """获取指定项目的全生命周期质量度量大盘与发版准入评估结果。"""
    _ = _user
    report = compute_quality_health_report(project_id=project_id)
    return report.to_dict()


@router.post("/metrics/evaluate")
async def evaluate_custom_quality_metrics_endpoint(
    body: EvaluateQualityMetricsIn,
    _user: User = Depends(get_current_user),
):
    """基于自定义度量参数推算四维加权质量健康得分与风险预警。"""
    _ = _user
    report = compute_quality_health_report(
        project_id=body.project_id,
        total_cases=body.total_cases,
        automated_cases=body.automated_cases,
        internal_defects=body.internal_defects,
        prod_escapes=body.prod_escapes,
        total_runs=body.total_runs,
        flaky_runs=body.flaky_runs,
        mttr_hours=body.mttr_hours,
    )
    return report.to_dict()
