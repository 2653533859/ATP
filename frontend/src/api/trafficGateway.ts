import http from './http'

export type TrafficProtocol = 'HTTP' | 'GRPC' | 'WEBSOCKET'

export interface CapturedTrafficItem {
  traffic_id: string
  protocol: TrafficProtocol
  method: string
  path_or_endpoint: string
  headers: Record<string, string>
  query_params: Record<string, string>
  request_body: string
  response_status_code: number
  response_body: string
  duration_ms: number
  client_ip: string | null
  tags: Record<string, string>
  captured_at: string
}

export interface CaptureFilterConfig {
  include_paths: string[]
  exclude_paths: string[]
  allowed_methods: string[]
  sampling_rate: number
  capture_request_body: boolean
  capture_response_body: boolean
  max_body_bytes: number
}

export interface CaptureMetrics {
  metrics: {
    total_intercepted: number
    total_captured: number
    total_filtered_out: number
    total_sampled_out: number
  }
  active_records_count: number
  protocol_breakdown: Record<string, number>
  filter_config: CaptureFilterConfig
}

export interface IngestTrafficRequest {
  protocol?: string
  method: string
  path_or_endpoint: string
  headers?: Record<string, string>
  query_params?: Record<string, string>
  request_body?: string
  response_status_code?: number
  response_body?: string
  duration_ms?: number
  client_ip?: string | null
  tags?: Record<string, string>
}

export interface ListTrafficParams {
  protocol?: string
  path_pattern?: string
  min_status?: number
  max_status?: number
  limit?: number
}

export type MaskingStrategy = 'MASK' | 'HASH' | 'REDACT'
export type SensitiveCategory = 'PHONE' | 'ID_CARD' | 'BANK_CARD' | 'EMAIL' | 'JWT_TOKEN' | 'PASSWORD' | 'CUSTOM'

export interface SensitiveRuleItem {
  rule_id: string
  name: string
  category: SensitiveCategory
  strategy: MaskingStrategy
  field_key_patterns: string[]
  custom_keywords?: string[]
  enabled: boolean
}

export interface TrafficClusterItem {
  cluster_id: string
  fingerprint: string
  protocol: string
  method: string
  normalized_path: string
  status_code: number
  sample_count: number
  representative_traffic_id: string
  extracted_dataset_rows: Array<Record<string, any>>
  source_traffic_ids: string[]
  schema_signature: string
}

export interface SynthesizedCaseItem {
  case_id: string
  cluster_id: string
  name: string
  description: string
  protocol: string
  method: string
  url_path: string
  headers: Record<string, string>
  query_params_template: Record<string, string>
  request_body_template: string
  assertions: Array<Record<string, any>>
  dataset_rows: Array<Record<string, any>>
  source_traffic_ids: string[]
  created_at: string
}

export interface SynthesisReportItem {
  report_id: string
  total_traffic_evaluated: number
  clusters_formed: number
  deduplication_ratio_pct: number
  synthesized_cases_count: number
  cases: SynthesizedCaseItem[]
  created_at: string
}

export interface RunSynthesisRequest {
  traffic_records?: Array<Record<string, any>>
  auto_mask_first?: boolean
  max_dataset_rows_per_case?: number
  case_name_prefix?: string
  protocol_filter?: string
  limit_captured?: number
}

export const trafficCaptureApi = {
  getFilterConfig(): Promise<CaptureFilterConfig> {
    return http.get('/traffic/capture/config')
  },

  updateFilterConfig(data: Partial<CaptureFilterConfig>): Promise<{ message: string; config: CaptureFilterConfig }> {
    return http.post('/traffic/capture/config', data)
  },

  interceptTraffic(data: IngestTrafficRequest): Promise<{ message: string; captured: boolean; item: CapturedTrafficItem | null }> {
    return http.post('/traffic/capture/intercept', data)
  },

  listRecords(params?: ListTrafficParams): Promise<{ total: number; records: CapturedTrafficItem[] }> {
    return http.get('/traffic/capture/records', { params })
  },

  getRecord(trafficId: string): Promise<CapturedTrafficItem> {
    return http.get(`/traffic/capture/records/${trafficId}`)
  },

  clearRecords(): Promise<{ message: string; deleted_count: number }> {
    return http.delete('/traffic/capture/records')
  },

  getMetrics(): Promise<CaptureMetrics> {
    return http.get('/traffic/capture/metrics')
  },
}

export const trafficMaskerApi = {
  getRules(): Promise<{ total: number; rules: SensitiveRuleItem[] }> {
    return http.get('/traffic/mask/rules')
  },

  updateRules(rules: SensitiveRuleItem[]): Promise<{ message: string; rules: SensitiveRuleItem[] }> {
    return http.put('/traffic/mask/rules', { rules })
  },

  resetRules(): Promise<{ message: string; rules: SensitiveRuleItem[] }> {
    return http.post('/traffic/mask/rules/reset')
  },

  maskText(data: { text: string; custom_keywords?: string[] }): Promise<{ original: string; masked: string }> {
    return http.post('/traffic/mask/text', data)
  },

  maskPayload(data: { payload: any; custom_keywords?: string[] }): Promise<{ masked_payload: any }> {
    return http.post('/traffic/mask/payload', data)
  },

  maskTrafficItem(data: { traffic_item: any; custom_keywords?: string[] }): Promise<{ message: string; item: any }> {
    return http.post('/traffic/mask/item', data)
  },

  batchMaskTraffic(data: { items: any[]; custom_keywords?: string[] }): Promise<{ message: string; total: number; items: any[] }> {
    return http.post('/traffic/mask/batch', data)
  },
}

export const trafficSynthesizerApi = {
  runSynthesis(data: RunSynthesisRequest): Promise<{ message: string; report: SynthesisReportItem }> {
    return http.post('/traffic/synthesize/run', data)
  },

  previewClusters(data: { traffic_records: any[] }): Promise<{ total_evaluated: number; clusters_formed: number; deduplication_ratio_pct: number; clusters: TrafficClusterItem[] }> {
    return http.post('/traffic/synthesize/cluster-preview', data)
  },

  listReports(): Promise<{ total: number; reports: SynthesisReportItem[] }> {
    return http.get('/traffic/synthesize/reports')
  },

  getReport(reportId: string): Promise<SynthesisReportItem> {
    return http.get(`/traffic/synthesize/reports/${reportId}`)
  },
}
