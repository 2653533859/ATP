"""Enterprise FinOps Multi-Tenant Compute and Storage Cost Reporting Service (Q4.3).

Provides:
1. Multi-tenant Worker compute resource consumption (CPU-core-hours) calculation.
2. MinIO and local test artifact storage space (GB-months) attribution.
3. Enterprise FinOps cost model with configurable unit rates.
4. CSV export and executive summary KPI generation for platform administrators.
"""

from __future__ import annotations

import csv
from datetime import datetime, timedelta, timezone
import io
import logging

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.apk import Apk
from app.models.performance import PerformanceRun
from app.models.plan import PlanRun, TestPlan
from app.models.project import Project
from app.models.suite import SuiteRun, TestSuite
from app.schemas.finops import FinOpsCostReportOut, FinOpsRates, ProjectCostItem

logger = logging.getLogger(__name__)

DEFAULT_CPU_HOUR_RATE = 0.25  # 0.25 CNY per CPU Core-Hour
DEFAULT_STORAGE_GB_MONTH_RATE = 0.12  # 0.12 CNY per GB-Month


async def get_project_compute_metrics(
    db: AsyncSession,
    project_id: int,
    start_time: datetime,
    end_time: datetime,
) -> tuple[int, float, float]:
    """Calculate total execution count, execution seconds, and equivalent CPU Core-Hours for a project.

    Returns:
        (total_runs, total_execution_seconds, cpu_hours)
    """
    total_runs = 0
    total_seconds = 0.0
    cpu_hours = 0.0

    # 1. Suite Runs (Standard test execution, baseline 1.0 vCPU Core)
    q_suite = (
        select(func.count(SuiteRun.id), func.coalesce(func.sum(SuiteRun.duration_ms), 0))
        .join(TestSuite, SuiteRun.suite_id == TestSuite.id)
        .where(
            TestSuite.project_id == project_id,
            SuiteRun.created_at >= start_time,
            SuiteRun.created_at <= end_time,
        )
    )
    s_count, s_ms = (await db.execute(q_suite)).one()
    total_runs += int(s_count or 0)
    suite_sec = float(s_ms or 0) / 1000.0
    total_seconds += suite_sec
    cpu_hours += (suite_sec * 1.0) / 3600.0

    # 2. Plan Runs (Multi-suite batch orchestration, baseline 1.5 vCPU Cores)
    q_plan = (
        select(func.count(PlanRun.id), func.coalesce(func.sum(PlanRun.duration_ms), 0))
        .join(TestPlan, PlanRun.plan_id == TestPlan.id)
        .where(
            TestPlan.project_id == project_id,
            PlanRun.created_at >= start_time,
            PlanRun.created_at <= end_time,
        )
    )
    p_count, p_ms = (await db.execute(q_plan)).one()
    total_runs += int(p_count or 0)
    plan_sec = float(p_ms or 0) / 1000.0
    total_seconds += plan_sec
    cpu_hours += (plan_sec * 1.5) / 3600.0

    # 3. Performance Runs (High-concurrency load testing, baseline 3.0 vCPU Cores)
    q_perf = select(PerformanceRun).where(
        PerformanceRun.project_id == project_id,
        PerformanceRun.created_at >= start_time,
        PerformanceRun.created_at <= end_time,
    )
    perf_runs = (await db.execute(q_perf)).scalars().all()
    total_runs += len(perf_runs)
    for pr in perf_runs:
        summary = pr.summary or {}
        # Try extracting duration from summary
        dur_sec = float(summary.get("duration_seconds", 60.0))
        total_seconds += dur_sec
        cpu_hours += (dur_sec * 3.0) / 3600.0

    return total_runs, round(total_seconds, 2), round(cpu_hours, 4)


async def get_project_storage_bytes(
    db: AsyncSession,
    project_id: int,
) -> int:
    """Calculate current storage bytes occupied by project APK assets and artifacts."""
    # 1. APK file sizes
    q_apk = select(func.coalesce(func.sum(Apk.file_size), 0)).where(Apk.project_id == project_id)
    apk_bytes = (await db.execute(q_apk)).scalar() or 0

    # Baseline storage attribution per project (reports, screenshots, traces estimated at ~50MB baseline)
    baseline_bytes = 50 * 1024 * 1024
    return int(apk_bytes + baseline_bytes)


def generate_optimization_tip(
    compute_cost: float,
    storage_cost: float,
    storage_gb: float,
    total_runs: int,
) -> str:
    """Generate intelligent FinOps cost optimization recommendations."""
    if storage_cost > compute_cost * 2.0 and storage_gb > 1.0:
        return f"存储成本占比显著偏高（{storage_gb:.2f} GB），建议配置 Q4.2 视频与截图短期清理策略以压缩开销。"
    elif total_runs > 50 and compute_cost > 10.0:
        return "执行量较高且计算开销较大，建议开启套件去重与增量变动测试，避免全量重复跑。"
    elif total_runs == 0:
        return "当前统计周期内无有效执行，建议归档闲置测试资产与环境。"
    else:
        return "资源配额利用良好，计算与存储配比健康。"


async def generate_finops_cost_report(
    db: AsyncSession,
    *,
    from_date: datetime | None = None,
    to_date: datetime | None = None,
    rates: FinOpsRates | None = None,
    project_id: int | None = None,
) -> FinOpsCostReportOut:
    """Generate comprehensive FinOps multi-tenant cost analysis report."""
    now_utc = datetime.now(timezone.utc)
    start_time = from_date or (now_utc - timedelta(days=30))
    end_time = to_date or now_utc

    active_rates = rates or FinOpsRates()
    period_days = max(1.0, (end_time - start_time).total_seconds() / 86400.0)

    # 1. Query projects
    q_projects = select(Project).where(Project.status == "active")
    if project_id is not None:
        q_projects = q_projects.where(Project.id == project_id)

    projects = (await db.execute(q_projects)).scalars().all()

    project_cost_items: list[ProjectCostItem] = []
    total_platform_cost = 0.0
    total_compute_cost = 0.0
    total_storage_cost = 0.0
    total_cpu_hours = 0.0
    total_storage_gb = 0.0

    for proj in projects:
        runs_count, exec_sec, cpu_hrs = await get_project_compute_metrics(db, proj.id, start_time, end_time)
        stor_bytes = await get_project_storage_bytes(db, proj.id)
        stor_gb = round(float(stor_bytes) / (1024**3), 4)

        comp_cost = round(cpu_hrs * active_rates.cpu_hour_rate, 2)
        # Storage cost prorated by period_days vs 30 days
        stor_cost = round(stor_gb * active_rates.storage_gb_month_rate * (period_days / 30.0), 2)
        proj_total_cost = round(comp_cost + stor_cost, 2)

        tip = generate_optimization_tip(comp_cost, stor_cost, stor_gb, runs_count)

        project_cost_items.append(
            ProjectCostItem(
                project_id=proj.id,
                project_name=proj.name,
                total_runs=runs_count,
                total_execution_seconds=exec_sec,
                cpu_hours=cpu_hrs,
                compute_cost=comp_cost,
                storage_bytes=stor_bytes,
                storage_gb=stor_gb,
                storage_cost=stor_cost,
                total_cost=proj_total_cost,
                cost_share_pct=0.0,  # calculated below
                optimization_tip=tip,
            )
        )

        total_platform_cost += proj_total_cost
        total_compute_cost += comp_cost
        total_storage_cost += stor_cost
        total_cpu_hours += cpu_hrs
        total_storage_gb += stor_gb

    # Sort descending by total cost
    project_cost_items.sort(key=lambda p: p.total_cost, reverse=True)

    # Calculate cost share percentage
    for item in project_cost_items:
        if total_platform_cost > 0:
            item.cost_share_pct = round((item.total_cost / total_platform_cost) * 100.0, 2)
        else:
            item.cost_share_pct = 0.0

    highest_project = project_cost_items[0].project_name if project_cost_items else None

    return FinOpsCostReportOut(
        period_start=start_time.isoformat(),
        period_end=end_time.isoformat(),
        currency="CNY",
        rates=active_rates,
        total_projects=len(project_cost_items),
        total_platform_cost=round(total_platform_cost, 2),
        total_compute_cost=round(total_compute_cost, 2),
        total_storage_cost=round(total_storage_cost, 2),
        total_cpu_hours=round(total_cpu_hours, 4),
        total_storage_gb=round(total_storage_gb, 4),
        highest_cost_project=highest_project,
        project_costs=project_cost_items,
    )


def export_finops_report_csv(report: FinOpsCostReportOut) -> str:
    """Format FinOpsCostReportOut into standard CSV with UTF-8 BOM."""
    output = io.StringIO()
    # Write UTF-8 BOM for Excel
    output.write("\ufeff")

    writer = csv.writer(output)
    writer.writerow(
        [
            "项目ID",
            "项目名称",
            "执行任务总数",
            "累计执行秒数",
            "CPU核时(Core-Hours)",
            f"计算成本({report.currency})",
            "存储空间(GB)",
            f"存储成本({report.currency})",
            f"总成本({report.currency})",
            "成本分摊比例(%)",
            "FinOps成本优化建议",
        ]
    )

    for p in report.project_costs:
        writer.writerow(
            [
                p.project_id,
                p.project_name,
                p.total_runs,
                f"{p.total_execution_seconds:.1f}",
                f"{p.cpu_hours:.4f}",
                f"{p.compute_cost:.2f}",
                f"{p.storage_gb:.4f}",
                f"{p.storage_cost:.2f}",
                f"{p.total_cost:.2f}",
                f"{p.cost_share_pct:.2f}%",
                p.optimization_tip,
            ]
        )

    return output.getvalue()
