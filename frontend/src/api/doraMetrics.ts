import http from './http'

export type DoraLevel = 'elite' | 'high' | 'medium' | 'low'

export interface DoraDimensionMetricItem {
  dimension_name: string
  value: number
  unit: string
  level: DoraLevel
  description: string
  benchmark_guideline: string
}

export interface DoraPerformanceReportItem {
  report_id: string
  project_id: number | null
  evaluation_period_days: number
  overall_maturity_level: DoraLevel
  dimensions: {
    deployment_frequency: DoraDimensionMetricItem
    lead_time_for_changes: DoraDimensionMetricItem
    change_failure_rate: DoraDimensionMetricItem
    time_to_restore_service: DoraDimensionMetricItem
  }
  test_on_time_completion_rate_pct: number
  bottlenecks_identified: string[]
  engineering_efficiency_recommendations: string[]
  evaluated_at: string
}

export interface EvaluateDoraRequest {
  project_id?: number | null
  evaluation_period_days?: number
  total_deployments_count?: number
  lead_time_for_changes_hours?: number
  change_failure_rate_pct?: number
  time_to_restore_service_minutes?: number
  test_runs_on_time_count?: number
  test_runs_total_count?: number
}

export const doraMetricsApi = {
  evaluate(data: EvaluateDoraRequest): Promise<{ message: string; report: DoraPerformanceReportItem }> {
    return http.post('/reporting/dora/evaluate', data)
  },

  listReports(params?: { project_id?: number }): Promise<{ total: number; reports: DoraPerformanceReportItem[] }> {
    return http.get('/reporting/dora/reports', { params })
  },

  getReport(reportId: string): Promise<DoraPerformanceReportItem> {
    return http.get(`/reporting/dora/reports/${reportId}`)
  },
}
