import http from './http'

export type ReleaseVerdict = 'APPROVED' | 'WARNING' | 'BLOCKED'
export type QualityGrade = 'A' | 'B' | 'C' | 'D'

export interface DimensionMetricDetail {
  score: number
  weight: number
  metrics: Record<string, any>
}

export interface QualityMetricsReport {
  project_id: number | null
  generated_at: string
  dimensions: {
    coverage: DimensionMetricDetail
    defect_escape: DimensionMetricDetail
    execution_stability: DimensionMetricDetail
    mttr: DimensionMetricDetail
  }
  composite_health_score: number
  grade: QualityGrade
  release_readiness: ReleaseVerdict
  actionable_recommendations: string[]
}

export interface EvaluateCustomMetricsRequest {
  project_id?: number | null
  total_cases?: number
  automated_cases?: number
  internal_defects?: number
  prod_escapes?: number
  total_runs?: number
  flaky_runs?: number
  mttr_hours?: number
}

export const qualityGovernanceApi = {
  getProjectMetrics(projectId: number): Promise<QualityMetricsReport> {
    return http.get(`/quality/metrics/project/${projectId}`)
  },

  evaluateCustomMetrics(data: EvaluateCustomMetricsRequest): Promise<QualityMetricsReport> {
    return http.post('/quality/metrics/evaluate', data)
  },
}
