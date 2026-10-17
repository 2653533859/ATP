import http from './http'

export interface MirroredTrafficItem {
  record_id: string
  trace_id: string
  method: string
  url: string
  path: string
  query_params: Record<string, any>
  headers: Record<string, string>
  status_code: number
  response_headers: Record<string, string>
  response_body: any
  duration_ms: number
  is_sanitized: boolean
  recorded_at: string
}

export interface TrafficReplayMetrics {
  total_received: number
  probes_filtered: number
  sampling_dropped: number
  recorded_count: number
  sanitized_count: number
}

export const trafficReplayApi = {
  sanitizePayload(data: { payload: Record<string, any>; mode?: string; salt?: string }): Promise<{
    message: string
    sanitized_payload: any
    audit_trail: any
  }> {
    return http.post('/traffic-replay/sanitize', data)
  },

  ingestMirrorTraffic(data: { raw_traffic: Record<string, any>; criteria?: Record<string, any> }): Promise<{
    should_record: boolean
    reason: string
    item: MirroredTrafficItem | null
  }> {
    return http.post('/traffic-replay/mirror/ingest', data)
  },

  listRecords(params?: { method?: string; path_pattern?: string; limit?: number }): Promise<{
    total: number
    records: MirroredTrafficItem[]
  }> {
    return http.get('/traffic-replay/records', { params })
  },

  getRecord(recordId: string): Promise<{ record: MirroredTrafficItem }> {
    return http.get(`/traffic-replay/record/${recordId}`)
  },

  getMetrics(): Promise<{
    metrics: TrafficReplayMetrics
    buffer_size: number
    buffer_capacity: number
  }> {
    return http.get('/traffic-replay/metrics')
  },

  batchReplay(data: { record_ids: string[]; target_host?: string; concurrency?: number }): Promise<{
    message: string
    dispatched_tasks: any[]
  }> {
    return http.post('/traffic-replay/batch-replay', data)
  },

  clearRecords(): Promise<{ message: string }> {
    return http.post('/traffic-replay/clear')
  },
  testNoiseRule(data: {
    rule: Record<string, any>
    test_json_path: string
    test_baseline_value?: any
    test_replayed_value?: any
  }): Promise<{ matched: boolean; reason: string; rule_summary: any }> {
    return http.post('/traffic-replay/noise-rule/test', data)
  },

  diffEvaluate(data: {
    record_id: string
    baseline_status_code: number
    baseline_body: any
    replayed_status_code: number
    replayed_body: any
    custom_rules?: any[]
  }): Promise<{
    raw_diff_report: any
    suppressed_report: any
    evaluation_result: any
  }> {
    return http.post('/traffic-replay/diff-evaluate', data)
  },
}
