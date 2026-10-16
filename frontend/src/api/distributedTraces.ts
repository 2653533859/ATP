import http from './http'

export type SpanKind = 'SERVER' | 'CLIENT' | 'PRODUCER' | 'CONSUMER' | 'INTERNAL'
export type SpanStatus = 'OK' | 'ERROR' | 'UNSET'

export interface DistributedSpanItem {
  span_id: string
  trace_id: string
  parent_span_id: string | null
  service_name: string
  operation_name: string
  kind: SpanKind
  start_time_us: number
  duration_us: number
  duration_ms: number
  self_time_ms: number
  status: SpanStatus
  is_slow: boolean
  attributes: Record<string, any>
}

export interface FlamegraphNodeItem {
  name: string
  value: number
  span_id: string
  service_name: string
  duration_ms: number
  self_time_ms: number
  is_slow: boolean
  status: string
  children: FlamegraphNodeItem[]
}

export interface TraceTreeReportItem {
  trace_id: string
  root_service: string
  root_operation: string
  total_spans_count: number
  total_duration_ms: number
  services_involved: string[]
  slow_spans_count: number
  slow_spans: DistributedSpanItem[]
  flamegraph_root: FlamegraphNodeItem
  spans_flat: DistributedSpanItem[]
  bottleneck_summary: string
  created_at: string
}

export interface IngestTraceRequest {
  trace_id: string
  spans: Array<Record<string, any>>
  slow_span_threshold_ms?: number
}

export const distributedTracesApi = {
  ingestTrace(data: IngestTraceRequest): Promise<{ message: string; report: TraceTreeReportItem }> {
    return http.post('/diagnostics/traces/ingest', data)
  },

  listTraces(params?: { service_name?: string }): Promise<{ total: number; traces: TraceTreeReportItem[] }> {
    return http.get('/diagnostics/traces', { params })
  },

  getTrace(traceId: string): Promise<TraceTreeReportItem> {
    return http.get(`/diagnostics/traces/${traceId}`)
  },
}
