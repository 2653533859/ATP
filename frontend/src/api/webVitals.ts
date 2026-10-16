import http from './http'

export type VitalRating = 'good' | 'needs_improvement' | 'poor'

export interface WebVitalMetric {
  name: string
  value: number
  unit: string
  rating: VitalRating
  good_threshold: number
  poor_threshold: number
  description: string
}

export interface BlockingResource {
  url: string
  resource_type: string
  duration_ms: number
  transfer_size_kb: number
  impact: 'high' | 'medium' | 'low'
  suggestion: string
}

export interface WebVitalsAuditReport {
  audit_id: string
  target_url: string
  browser_type: string
  device_emulation: string
  overall_performance_score: number
  overall_rating: VitalRating
  core_vitals: Record<string, WebVitalMetric>
  supplementary_vitals: Record<string, WebVitalMetric>
  blocking_resources: BlockingResource[]
  optimization_recommendations: string[]
  evaluated_at: string
}

export interface DiagnoseWebVitalsRequest {
  target_url: string
  lcp_ms?: number
  inp_ms?: number
  cls_score?: number
  fcp_ms?: number
  ttfb_ms?: number
  tbt_ms?: number
  raw_resources?: Array<Record<string, any>>
  browser_type?: string
  device_emulation?: string
}

export const webVitalsApi = {
  diagnose(data: DiagnoseWebVitalsRequest): Promise<{ message: string; report: WebVitalsAuditReport }> {
    return http.post('/diagnostics/web-vitals/diagnose', data)
  },

  listReports(): Promise<{ total: number; reports: WebVitalsAuditReport[] }> {
    return http.get('/diagnostics/web-vitals/reports')
  },

  getReport(auditId: string): Promise<WebVitalsAuditReport> {
    return http.get(`/diagnostics/web-vitals/reports/${auditId}`)
  },
}
