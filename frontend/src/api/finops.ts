import http from './http'

export interface FinOpsRates {
  cpu_hour_rate: number
  storage_gb_month_rate: number
}

export interface ProjectCostItem {
  project_id: number
  project_name: string
  total_runs: number
  total_execution_seconds: number
  cpu_hours: number
  compute_cost: number
  storage_bytes: number
  storage_gb: number
  storage_cost: number
  total_cost: number
  cost_share_pct: number
  optimization_tip: string
}

export interface FinOpsCostReport {
  period_start: string
  period_end: string
  currency: string
  rates: FinOpsRates
  total_projects: number
  total_platform_cost: number
  total_compute_cost: number
  total_storage_cost: number
  total_cpu_hours: number
  total_storage_gb: number
  highest_cost_project?: string | null
  project_costs: ProjectCostItem[]
}

export interface FinOpsCostReportQuery {
  project_id?: number | null
  from_date?: string | null
  to_date?: string | null
  cpu_hour_rate?: number
  storage_gb_month_rate?: number
}

export const finopsApi = {
  getCostReport: (params?: FinOpsCostReportQuery) =>
    http.get<unknown, FinOpsCostReport>('/finops/cost-report', { params }),
  exportCostReportCsv: (params?: FinOpsCostReportQuery) =>
    http.get<unknown, Blob>('/finops/cost-report/export', { params, responseType: 'blob' }),
}
