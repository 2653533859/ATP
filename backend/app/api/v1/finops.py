"""Enterprise FinOps Cost Analysis and Report Export Endpoints (Q4.3)."""

from __future__ import annotations

from datetime import datetime
from fastapi import APIRouter, Depends, Query, Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, require_admin
from app.core.database import get_db
from app.models.user import User
from app.schemas.finops import FinOpsCostReportOut, FinOpsRates
from app.services.finops_cost_reporter import (
    DEFAULT_CPU_HOUR_RATE,
    DEFAULT_STORAGE_GB_MONTH_RATE,
    export_finops_report_csv,
    generate_finops_cost_report,
)

router = APIRouter(prefix="/finops", tags=["FinOps 成本分析"])


@router.get("/cost-report", response_model=FinOpsCostReportOut)
async def get_finops_cost_report_endpoint(
    project_id: int | None = Query(default=None, description="可选指定项目ID"),
    from_date: datetime | None = Query(default=None, description="起始日期 (UTC)"),
    to_date: datetime | None = Query(default=None, description="结束日期 (UTC)"),
    cpu_hour_rate: float = Query(default=DEFAULT_CPU_HOUR_RATE, ge=0.0, description="CPU核时单价(CNY)"),
    storage_gb_month_rate: float = Query(
        default=DEFAULT_STORAGE_GB_MONTH_RATE, ge=0.0, description="存储GB-月单价(CNY)"
    ),
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_user),
):
    """获取企业级多租户计算与存储资源成本统计报表。"""
    rates = FinOpsRates(
        cpu_hour_rate=cpu_hour_rate,
        storage_gb_month_rate=storage_gb_month_rate,
    )
    return await generate_finops_cost_report(
        db,
        from_date=from_date,
        to_date=to_date,
        rates=rates,
        project_id=project_id,
    )


@router.get("/cost-report/export")
async def export_finops_cost_report_csv_endpoint(
    project_id: int | None = Query(default=None, description="可选指定项目ID"),
    from_date: datetime | None = Query(default=None, description="起始日期 (UTC)"),
    to_date: datetime | None = Query(default=None, description="结束日期 (UTC)"),
    cpu_hour_rate: float = Query(default=DEFAULT_CPU_HOUR_RATE, ge=0.0, description="CPU核时单价(CNY)"),
    storage_gb_month_rate: float = Query(
        default=DEFAULT_STORAGE_GB_MONTH_RATE, ge=0.0, description="存储GB-月单价(CNY)"
    ),
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_admin),
):
    """导出企业级 FinOps 成本分摊与账单报表为 Excel 兼容的 CSV 文件。"""
    rates = FinOpsRates(
        cpu_hour_rate=cpu_hour_rate,
        storage_gb_month_rate=storage_gb_month_rate,
    )
    report = await generate_finops_cost_report(
        db,
        from_date=from_date,
        to_date=to_date,
        rates=rates,
        project_id=project_id,
    )
    csv_content = export_finops_report_csv(report)

    filename = f"finops-cost-report-{datetime.now().strftime('%Y%m%d%H%M%S')}.csv"
    return Response(
        content=csv_content,
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
