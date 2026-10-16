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

export type WriteGuardMode = 'BLOCK_WRITES' | 'SHADOW_HEADER_ONLY' | 'ALLOW_ALL' | 'DRY_RUN'

export interface MockRuleConfigItem {
  rule_id: string
  name: string
  pattern: string
  mock_status_code: number
  mock_response_body: string
  mock_headers?: Record<string, string>
  enabled: boolean
}

export interface ReplayItemResult {
  item_id: string
  traffic_id: string
  method: string
  path_or_endpoint: string
  executed_url: string
  original_status_code: number
  replayed_status_code: number
  duration_ms: number
  was_mocked: boolean
  mock_reason: string | null
  was_write_blocked: boolean
  replayed_response_body: string
  success: boolean
  error_message: string | null
}

export interface ReplaySessionReport {
  session_id: string
  target_base_url: string
  write_guard_mode: string
  total_items: number
  success_count: number
  failure_count: number
  blocked_write_count: number
  mocked_external_count: number
  avg_duration_ms: number
  results: ReplayItemResult[]
  created_at: string
}

export interface RunShadowReplayRequest {
  target_base_url?: string
  write_guard_mode?: WriteGuardMode | string
  rate_limit_qps?: number
  timeout_sec?: number
  inject_headers?: Record<string, string>
  external_mock_rules?: MockRuleConfigItem[]
  stop_on_error?: boolean
  traffic_records?: Array<Record<string, any>>
  limit_captured?: number
}

export type DiffType = 'ADDED' | 'DELETED' | 'MODIFIED' | 'TYPE_CHANGED'
export type DiffSeverity = 'CRITICAL' | 'WARNING' | 'INFO'

export interface DiffItem {
  path: string
  diff_type: DiffType
  severity: DiffSeverity
  baseline_value: any
  replayed_value: any
  description: string
}

export interface TrafficDiffReport {
  report_id: string
  similarity_score_pct: number
  is_identical: boolean
  total_differences_count: number
  critical_diffs_count: number
  warning_diffs_count: number
  ignored_noise_fields_count: number
  differences: DiffItem[]
  diff_summary: string
  baseline_status_code: number
  replayed_status_code: number
  created_at: string
}

export interface CompareResponsesRequest {
  baseline_response: any
  replayed_response: any
  baseline_status_code?: number
  replayed_status_code?: number
  noise_config?: {
    ignore_keys?: string[]
    ignore_paths?: string[]
    auto_detect_uuid?: boolean
    auto_detect_timestamp?: boolean
  }
}

export type DriftAlertLevel = 'NORMAL' | 'WARNING' | 'CRITICAL'

export interface GoldenBaselineItem {
  baseline_id: string
  endpoint: string
  protocol: string
  version_tag: string
  description: string
  golden_request_body: string
  golden_response_status: number
  golden_response_body: string
  tolerance_threshold_pct: number
  is_active: boolean
  tags: Record<string, string>
  created_at: string
  updated_at: string
}

export interface BaselineVerificationResult {
  verification_id: string
  baseline_id: string
  version_tag: string
  endpoint: string
  actual_status_code: number
  similarity_score_pct: number
  tolerance_threshold_pct: number
  passed: boolean
  diff_report_id: string
  critical_diffs_count: number
  warning_diffs_count: number
  alert_level: DriftAlertLevel
  summary: string
  verified_at: string
}

export interface BatchVerificationReport {
  batch_id: string
  total_verified: number
  passed_count: number
  drifted_count: number
  pass_rate_pct: number
  results: BaselineVerificationResult[]
  created_at: string
}

export interface CreateGoldenBaselineRequest {
  endpoint: string
  golden_response_body: any
  golden_response_status?: number
  golden_request_body?: string
  protocol?: string
  version_tag?: string
  description?: string
  tolerance_threshold_pct?: number
  is_active?: boolean
  baseline_id?: string
  tags?: Record<string, string>
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

export const shadowReplayApi = {
  runReplay(data: RunShadowReplayRequest): Promise<{ message: string; report: ReplaySessionReport }> {
    return http.post('/traffic/replay/run', data)
  },

  listSessions(): Promise<{ total: number; sessions: ReplaySessionReport[] }> {
    return http.get('/traffic/replay/sessions')
  },

  getSession(sessionId: string): Promise<ReplaySessionReport> {
    return http.get(`/traffic/replay/sessions/${sessionId}`)
  },

  getDefaultMockRules(): Promise<{ rules: MockRuleConfigItem[] }> {
    return http.get('/traffic/replay/mock-rules/defaults')
  },

  clearSessions(): Promise<{ message: string; deleted_count: number }> {
    return http.delete('/traffic/replay/sessions')
  },
}

export const trafficDiffApi = {
  compareResponses(data: CompareResponsesRequest): Promise<{ message: string; report: TrafficDiffReport }> {
    return http.post('/traffic/diff/compare', data)
  },

  compareTrafficIds(data: { baseline_traffic_id: string; replayed_traffic_id: string; noise_config?: any }): Promise<{ message: string; report: TrafficDiffReport }> {
    return http.post('/traffic/diff/compare-traffic-ids', data)
  },

  listReports(): Promise<{ total: number; reports: TrafficDiffReport[] }> {
    return http.get('/traffic/diff/reports')
  },

  getReport(reportId: string): Promise<TrafficDiffReport> {
    return http.get(`/traffic/diff/reports/${reportId}`)
  },

  getDefaultNoiseRules(): Promise<{ ignore_keys: string[]; ignore_paths: string[]; auto_detect_uuid: boolean; auto_detect_timestamp: boolean }> {
    return http.get('/traffic/diff/noise-rules/defaults')
  },

  clearReports(): Promise<{ message: string; deleted_count: number }> {
    return http.delete('/traffic/diff/reports')
  },
}

export const goldenBaselineApi = {
  createBaseline(data: CreateGoldenBaselineRequest): Promise<{ message: string; baseline: GoldenBaselineItem }> {
    return http.post('/traffic/golden-baselines', data)
  },

  listBaselines(params?: { endpoint?: string; version_tag?: string; is_active?: boolean }): Promise<{ total: number; baselines: GoldenBaselineItem[] }> {
    return http.get('/traffic/golden-baselines', { params })
  },

  getBaseline(baselineId: string): Promise<GoldenBaselineItem> {
    return http.get(`/traffic/golden-baselines/${baselineId}`)
  },

  deleteBaseline(baselineId: string): Promise<{ message: string; baseline_id: string }> {
    return http.delete(`/traffic/golden-baselines/${baselineId}`)
  },

  verifySingle(data: { baseline_id: string; actual_response_body: any; actual_status_code?: number; custom_tolerance_pct?: number }): Promise<{ message: string; result: BaselineVerificationResult }> {
    return http.post('/traffic/golden-baselines/verify', data)
  },

  batchVerify(data: { items: any[]; default_version_tag?: string }): Promise<{ message: string; report: BatchVerificationReport }> {
    return http.post('/traffic/golden-baselines/batch-verify', data)
  },

  listBatchReports(): Promise<{ total: number; reports: BatchVerificationReport[] }> {
    return http.get('/traffic/golden-baselines/batch-reports')
  },

  getBatchReport(batchId: string): Promise<BatchVerificationReport> {
    return http.get(`/traffic/golden-baselines/batch-reports/${batchId}`)
  },
}
