"""FinOps Multi-Tenant Resource Cost Analysis Schemas (Q4.3)."""

from __future__ import annotations

from pydantic import BaseModel, Field


class FinOpsRates(BaseModel):
    cpu_hour_rate: float = Field(default=0.25, ge=0.0, description="Cost per CPU-core-hour in CNY")
    storage_gb_month_rate: float = Field(default=0.12, ge=0.0, description="Cost per GB-month in CNY")


class ProjectCostItem(BaseModel):
    project_id: int
    project_name: str
    total_runs: int
    total_execution_seconds: float
    cpu_hours: float
    compute_cost: float
    storage_bytes: int
    storage_gb: float
    storage_cost: float
    total_cost: float
    cost_share_pct: float
    optimization_tip: str


class FinOpsCostReportOut(BaseModel):
    period_start: str
    period_end: str
    currency: str = "CNY"
    rates: FinOpsRates
    total_projects: int
    total_platform_cost: float
    total_compute_cost: float
    total_storage_cost: float
    total_cpu_hours: float
    total_storage_gb: float
    highest_cost_project: str | None = None
    project_costs: list[ProjectCostItem]
