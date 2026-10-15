"""Unit tests for Q4.3 Enterprise FinOps Cost Analysis and Report Export.

Tests:
1. get_project_compute_metrics aggregates execution seconds and CPU core-hours
2. generate_optimization_tip provides intelligent recommendations
3. generate_finops_cost_report computes multi-tenant costs and share percentages
4. export_finops_report_csv generates valid CSV with UTF-8 BOM and standard columns
"""

from __future__ import annotations

import csv
from datetime import datetime, timezone
import io
from types import SimpleNamespace
from typing import Any

import pytest

from app.models.bootstrap import load_all_models
from app.models.project import Project
from app.schemas.finops import FinOpsCostReportOut, FinOpsRates, ProjectCostItem
from app.services.finops_cost_reporter import (
    export_finops_report_csv,
    generate_finops_cost_report,
    generate_optimization_tip,
    get_project_compute_metrics,
)

load_all_models()


@pytest.mark.asyncio
async def test_get_project_compute_metrics():
    # Mock SuiteRun: 5 runs, 3,600,000 ms (3600s = 1 hr) -> 1.0 CPU Core -> 1.0 core-hour
    # Mock PlanRun: 2 runs, 7,200,000 ms (7200s = 2 hr) -> 1.5 Cores -> 3.0 core-hours
    # Mock PerformanceRun: 1 run, 1800s -> 3.0 Cores -> 1.5 core-hours
    # Total: 8 runs, 12600s, 5.5 core-hours
    perf_run = SimpleNamespace(summary={"duration_seconds": 1800.0})

    class _MockDB:
        async def execute(self, stmt):
            sql = str(stmt).lower()
            if "from suite_runs" in sql:
                return SimpleNamespace(one=lambda: (5, 3600000))
            if "from plan_runs" in sql:
                return SimpleNamespace(one=lambda: (2, 7200000))
            if "from performance_runs" in sql:
                return SimpleNamespace(scalars=lambda: SimpleNamespace(all=lambda: [perf_run]))
            return SimpleNamespace(one=lambda: (0, 0), scalars=lambda: SimpleNamespace(all=lambda: []))

    db: Any = _MockDB()
    now = datetime(2026, 10, 16, 12, 0, 0, tzinfo=timezone.utc)
    runs, sec, cpu_hrs = await get_project_compute_metrics(db, project_id=1, start_time=now, end_time=now)

    assert runs == 8
    assert sec == 12600.0
    assert cpu_hrs == 5.5


def test_generate_optimization_tip():
    # 1. High storage cost tip
    tip1 = generate_optimization_tip(compute_cost=2.0, storage_cost=10.0, storage_gb=5.0, total_runs=10)
    assert "存储成本占比显著偏高" in tip1
    assert "Q4.2" in tip1

    # 2. High compute runs tip
    tip2 = generate_optimization_tip(compute_cost=50.0, storage_cost=2.0, storage_gb=0.2, total_runs=80)
    assert "执行量较高且计算开销较大" in tip2

    # 3. Inactive project tip
    tip3 = generate_optimization_tip(compute_cost=0.0, storage_cost=0.5, storage_gb=0.1, total_runs=0)
    assert "无有效执行" in tip3

    # 4. Balanced healthy tip
    tip4 = generate_optimization_tip(compute_cost=5.0, storage_cost=3.0, storage_gb=0.5, total_runs=20)
    assert "资源配额利用良好" in tip4


@pytest.mark.asyncio
async def test_generate_finops_cost_report():
    p1 = Project(id=1, name="E-Commerce Core", status="active")
    p2 = Project(id=2, name="Mobile App", status="active")

    class _MockDB:
        async def execute(self, stmt):
            sql = str(stmt).lower()
            if "from projects" in sql:
                return SimpleNamespace(scalars=lambda: SimpleNamespace(all=lambda: [p1, p2]))
            if "from apks" in sql:
                return SimpleNamespace(scalar=lambda: 100 * 1024 * 1024)  # 100MB
            if "from suite_runs" in sql:
                return SimpleNamespace(one=lambda: (10, 36000000))  # 36000s = 10 hrs
            if "from plan_runs" in sql:
                return SimpleNamespace(one=lambda: (0, 0))
            if "from performance_runs" in sql:
                return SimpleNamespace(scalars=lambda: SimpleNamespace(all=lambda: []))
            return SimpleNamespace(one=lambda: (0, 0), scalars=lambda: SimpleNamespace(all=lambda: []))

    db: Any = _MockDB()
    rates = FinOpsRates(cpu_hour_rate=0.50, storage_gb_month_rate=0.20)
    report = await generate_finops_cost_report(db, rates=rates)

    assert report.total_projects == 2
    assert report.currency == "CNY"
    assert report.rates.cpu_hour_rate == 0.50
    assert report.total_platform_cost > 0.0
    assert report.total_cpu_hours > 0.0
    assert len(report.project_costs) == 2
    assert report.highest_cost_project in {"E-Commerce Core", "Mobile App"}

    # Total cost share percentage must sum to ~100%
    total_share = sum(p.cost_share_pct for p in report.project_costs)
    assert abs(total_share - 100.0) < 0.5


def test_export_finops_report_csv():
    report = FinOpsCostReportOut(
        period_start="2026-09-16T00:00:00Z",
        period_end="2026-10-16T00:00:00Z",
        currency="CNY",
        rates=FinOpsRates(cpu_hour_rate=0.25, storage_gb_month_rate=0.12),
        total_projects=1,
        total_platform_cost=15.50,
        total_compute_cost=10.00,
        total_storage_cost=5.50,
        total_cpu_hours=40.0,
        total_storage_gb=45.83,
        highest_cost_project="Payment Gateway",
        project_costs=[
            ProjectCostItem(
                project_id=10,
                project_name="Payment Gateway",
                total_runs=25,
                total_execution_seconds=36000.0,
                cpu_hours=40.0,
                compute_cost=10.00,
                storage_bytes=49214455808,
                storage_gb=45.83,
                storage_cost=5.50,
                total_cost=15.50,
                cost_share_pct=100.0,
                optimization_tip="存储成本占比显著偏高",
            )
        ],
    )

    csv_data = export_finops_report_csv(report)
    # 1. Must start with UTF-8 BOM
    assert csv_data.startswith("\ufeff")

    # 2. Parse CSV
    reader = csv.reader(io.StringIO(csv_data.lstrip("\ufeff")))
    rows = list(reader)
    assert len(rows) == 2  # 1 header + 1 project row

    header = rows[0]
    assert "项目ID" in header
    assert "CPU核时(Core-Hours)" in header
    assert "总成本(CNY)" in header

    proj_row = rows[1]
    assert proj_row[0] == "10"
    assert proj_row[1] == "Payment Gateway"
    assert proj_row[2] == "25"
    assert proj_row[8] == "15.50"
    assert proj_row[9] == "100.00%"
