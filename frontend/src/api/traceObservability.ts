import http from './http'

export interface TelemetrySpanItem {
  trace_id: string
  span_id: string
  parent_span_id: string | null
  name: string
  service_name: string
  kind: string
  start_time_us: number
  end_time_us: number
  duration_ms: number
  status_code: 'OK' | 'ERROR' | 'UNSET'
  status_message: string
  attributes: Record<string, any>
  events: Array<Record<string, any>>
  depth?: number
  children?: TelemetrySpanItem[]
}

export interface TraceTreeReport {
  trace_id: string
  root_span_id: string
  total_spans_count: number
  total_duration_ms: number
  services_involved: string[]
  has_error: boolean
  root_nodes: TelemetrySpanItem[]
  extracted_at: string
}

export interface TraceSummaryItem {
  trace_id: string
  root_span_id: string
  root_operation: string
  root_service: string
  total_spans_count: number
  total_duration_ms: number
  services_involved: string[]
  has_error: boolean
  extracted_at: string
}

export interface CriticalPathSpanItem {
  span_id: string
  parent_span_id: string | null
  name: string
  service_name: string
  duration_ms: number
  self_time_ms: number
  critical_path_ratio_pct: number
  is_bottleneck: boolean
  bottleneck_category: string
}

export interface TraceFlamegraphNodeItem {
  name: string
  value: number
  self_value: number
  service_name: string
  span_id: string
  is_critical_path: boolean
  is_bottleneck: boolean
  bottleneck_category: string
  children: TraceFlamegraphNodeItem[]
}

export interface CriticalPathProfileReport {
  trace_id: string
  total_trace_duration_ms: number
  critical_path_duration_ms: number
  critical_path_spans_count: number
  critical_path: CriticalPathSpanItem[]
  flamegraph_root: TraceFlamegraphNodeItem
  diagnosis_summary: string
  profiled_at: string
}

export interface AnomalyClusterItem {
  cluster_id: string
  service_name: string
  operation_name: string
  pattern: string
  occurrences_count: number
  avg_duration_ms: number
  p95_duration_ms: number
  max_duration_ms: number
  deviation_sigma: number
  error_ratio_pct: number
  impact_score: number
  root_cause_explanation: string
  actionable_recommendations: string[]
  sample_trace_ids: string[]
}

export interface TraceAnomalyClusterReport {
  total_spans_analyzed: number
  total_anomalies_detected: number
  clusters_count: number
  clusters: AnomalyClusterItem[]
  verdict_summary: string
  analyzed_at: string
}

export const traceTelemetryApi = {
  ingestSpans(spans: any[]): Promise<{ message: string; ingested_count: number; traces_updated_count: number; trace_ids: string[] }> {
    return http.post('/trace/telemetry/spans', { spans })
  },

  listTraces(params?: { limit?: number; service_name?: string; has_error?: boolean; min_duration_ms?: number }): Promise<{ total: number; traces: TraceSummaryItem[] }> {
    return http.get('/trace/telemetry/traces', { params })
  },

  getTraceTree(traceId: string): Promise<TraceTreeReport> {
    return http.get(`/trace/telemetry/traces/${traceId}`)
  },

  clearTraces(): Promise<{ message: string; cleared_count: number }> {
    return http.delete('/trace/telemetry/traces')
  },
}

export const traceFlamegraphApi = {
  profileById(traceId: string): Promise<CriticalPathProfileReport> {
    return http.get(`/trace/flamegraph/profile/${traceId}`)
  },

  profileSpans(data: { trace_id?: string; spans: any[] }): Promise<CriticalPathProfileReport> {
    return http.post('/trace/flamegraph/profile-spans', data)
  },
}

export const traceAnomalyApi = {
  analyze(data: { spans: any[]; slow_threshold_ms?: number }): Promise<TraceAnomalyClusterReport> {
    return http.post('/trace/anomaly-cluster/analyze', data)
  },

  telemetryDiagnose(params?: { slow_threshold_ms?: number }): Promise<TraceAnomalyClusterReport> {
    return http.get('/trace/anomaly-cluster/telemetry', { params })
  },
}
