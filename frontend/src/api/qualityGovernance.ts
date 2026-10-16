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

export type RuleOperator = 'gte' | 'lte' | 'gt' | 'lt' | 'eq'
export type RuleSeverity = 'blocker' | 'warning'

export interface QualityGateRuleItem {
  metric_key: string
  operator: RuleOperator
  threshold: number
  severity: RuleSeverity
  description?: string
}

export interface QualityGateProfileItem {
  profile_id: string
  name: string
  description: string
  rules: QualityGateRuleItem[]
  block_on_failure: boolean
}

export interface GateRuleEvaluationResult {
  metric_key: string
  operator: string
  threshold: number
  actual_value: number
  severity: RuleSeverity
  passed: boolean
  reason: string
}

export interface GateEvaluationResponse {
  profile_id: string
  verdict: ReleaseVerdict
  passed: boolean
  exit_code: number
  failed_blockers: string[]
  failed_warnings: string[]
  rule_results: GateRuleEvaluationResult[]
  evaluated_at: string
}

export interface CreateGateProfileRequest {
  profile_id: string
  name: string
  description?: string
  rules: QualityGateRuleItem[]
  block_on_failure?: boolean
}

export const qualityGovernanceApi = {
  getProjectMetrics(projectId: number): Promise<QualityMetricsReport> {
    return http.get(`/quality/metrics/project/${projectId}`)
  },

  evaluateCustomMetrics(data: EvaluateCustomMetricsRequest): Promise<QualityMetricsReport> {
    return http.post('/quality/metrics/evaluate', data)
  },

  listGateProfiles(): Promise<{ total: number; profiles: QualityGateProfileItem[] }> {
    return http.get('/quality/gates/profiles')
  },

  registerGateProfile(data: CreateGateProfileRequest): Promise<{ message: string; profile: QualityGateProfileItem }> {
    return http.post('/quality/gates/profiles', data)
  },

  evaluateQualityGate(profileId: string, metrics: Record<string, any>): Promise<GateEvaluationResponse> {
    return http.post('/quality/gates/evaluate', { profile_id: profileId, metrics })
  },
}
