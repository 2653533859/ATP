"""研发效能与 DORA 四维效能度量分析 API (D4.3)."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field

from app.api.deps import get_current_user, require_engineer
from app.models.user import User
from app.services.dora_metrics_calculator import (
    compute_dora_metrics,
    get_dora_report,
    list_dora_reports,
)

router = APIRouter(prefix="/reporting/dora", tags=["团队研发效能 DORA 度量分析"])


class EvaluateDoraIn(BaseModel):
    project_id: int | None = Field(default=None, description="项目 ID")
    evaluation_period_days: int = Field(default=30, ge=1, le=365, description="评估周期天数 (默认 30 天)")
    total_deployments_count: int = Field(default=45, ge=0, description="周期内测试与发布部署总次数")
    lead_time_for_changes_hours: float = Field(default=0.8, ge=0.0, description="代码提交至验证通过平均前置用时 (小时)")
    change_failure_rate_pct: float = Field(default=4.2, ge=0.0, le=100.0, description="发布变更失败与回滚率 (%)")
    time_to_restore_service_minutes: float = Field(default=35.0, ge=0.0, description="故障平均恢复时长 MTTR (分钟)")
    test_runs_on_time_count: int = Field(default=95, ge=0, description="按计划准时完成的测试执行轮次")
    test_runs_total_count: int = Field(default=100, ge=1, description="测试执行总轮次")


@router.post("/evaluate")
async def evaluate_dora_metrics_endpoint(
    body: EvaluateDoraIn,
    _user: User = Depends(require_engineer),
) -> dict[str, Any]:
    """计算四维 DORA 研发效能指标、团队成熟度等级与瓶颈优化建议 (需工程师权限)。"""
    _ = _user
    report = compute_dora_metrics(
        project_id=body.project_id,
        evaluation_period_days=body.evaluation_period_days,
        total_deployments_count=body.total_deployments_count,
        lead_time_for_changes_hours=body.lead_time_for_changes_hours,
        change_failure_rate_pct=body.change_failure_rate_pct,
        time_to_restore_service_minutes=body.time_to_restore_service_minutes,
        test_runs_on_time_count=body.test_runs_on_time_count,
        test_runs_total_count=body.test_runs_total_count,
    )
    return {"message": "DORA 研发效能度量计算完成", "report": report.to_dict()}


@router.get("/reports")
async def list_dora_reports_endpoint(
    project_id: int | None = Query(default=None, description="按项目 ID 筛选"),
    _user: User = Depends(get_current_user),
) -> dict[str, Any]:
    """查询历史 DORA 效能分析报告列表。"""
    _ = _user
    reports = list_dora_reports(project_id=project_id)
    return {"total": len(reports), "reports": [r.to_dict() for r in reports]}


@router.get("/reports/{report_id}")
async def get_dora_report_endpoint(
    report_id: str,
    _user: User = Depends(get_current_user),
) -> dict[str, Any]:
    """获取指定 DORA 效能分析报告详情。"""
    _ = _user
    report = get_dora_report(report_id)
    if not report:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"DORA 报告不存在: {report_id}")
    return report.to_dict()
