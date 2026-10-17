import http from './http'

export interface TraceContextDTO {
  trace_id: string
  span_id: string
  parent_span_id?: string | null
  sampled: boolean
  tracestate?: string
  traceparent: string
}

export interface ClockSkewCompensationResult {
  span_id: string
  service_name: string
  client_send_time_ms: number
  client_receive_time_ms: number
  raw_server_start_ms: number
  raw_server_end_ms: number
  skew_offset_ms: number
  estimated_rtt_ms: number
  calibrated_server_start_ms: number
  calibrated_server_end_ms: number
  is_skew_detected: boolean
  causality_preserved: boolean
  calibrated_at: string
}

export interface AlignedSpanItem {
  span_id: string
  parent_span_id?: string | null
  service_name: string
  name: string
  start_time_ms: number
  end_time_ms: number
  duration_ms: number
  clock_skew_compensated?: boolean
  applied_skew_ms?: number
  attributes?: Record<string, any>
  status?: { code: string; message?: string }
}

export interface SlowQueryDTO {
  span_id: string
  service_name: string
  db_system: string
  duration_ms: number
  statement: string
}

export interface RootCauseDiagnosisDTO {
  trace_id: string
  step_name: string
  step_status: string
  attribution_type: string
  root_cause_service: string
  root_cause_span_id: string
  root_cause_span_name: string
  error_message: string
  stack_trace: string
  slow_queries: SlowQueryDTO[]
  total_spans_analyzed: number
  error_spans_count: number
  diagnosis_summary: string
  suggested_action: string
  diagnosed_at: string
}

export interface TopologyNodeDTO {
  service_name: string
  service_type: string
  protocol: string
  span_count: number
  total_duration_ms: number
  avg_duration_ms: number
  error_count: number
  error_rate: number
}

export interface TopologyEdgeDTO {
  source_service: string
  target_service: string
  protocol: string
  call_count: number
  avg_latency_ms: number
}

export interface SpanTreeNodeDTO {
  span_id: string
  name: string
  service_name: string
  service_type: string
  protocol: string
  depth: number
  start_time_ms: number
  end_time_ms: number
  duration_ms: number
  self_time_ms: number
  children: SpanTreeNodeDTO[]
}

export interface TraceTopologyLineageDTO {
  trace_id: string
  total_spans: number
  services_count: number
  max_depth_hops: number
  protocols_covered: string[]
  root_service: string
  nodes: TopologyNodeDTO[]
  edges: TopologyEdgeDTO[]
  hierarchical_tree: SpanTreeNodeDTO[]
  critical_path_span_ids: string[]
  built_at: string
}

export const observabilityTraceApi = {
  compensateClockSkew(payload: {
    client_step_span: Record<string, any>
    server_spans: Record<string, any>[]
    service_name?: string
  }): Promise<{
    message: string
    calibration: ClockSkewCompensationResult
    aligned_spans: AlignedSpanItem[]
  }> {
    return http.post('/observability/trace/skew-compensate', payload)
  },

  deepDiveAnalysis(payload: {
    step_context: Record<string, any>
    spans: Record<string, any>[]
    slow_query_threshold_ms?: number
  }): Promise<{
    message: string
    diagnosis: RootCauseDiagnosisDTO
  }> {
    return http.post('/observability/trace/deep-dive', payload)
  },

  buildLineage(payload: {
    trace_id: string
    spans: Record<string, any>[]
  }): Promise<{
    message: string
    lineage: TraceTopologyLineageDTO
  }> {
    return http.post('/observability/trace/lineage', payload)
  },

  getLineage(traceId: string): Promise<{ lineage: TraceTopologyLineageDTO }> {
    return http.get(`/observability/trace/lineage/${traceId}`)
  },

  listLineages(limit: number = 50): Promise<{
    total: number
    lineages: TraceTopologyLineageDTO[]
  }> {
    return http.get('/observability/trace/lineages', { params: { limit } })
  },

  getExecutionTrail(runId: string): Promise<{
    session: {
      session_id: string
      run_id: string
      root_trace_id: string
      steps_count: number
      steps: Array<{
        step_index: number
        step_name: string
        step_span_id: string
        traceparent: string
        timestamp: string
      }>
    }
  }> {
    return http.get(`/observability/trace/trail/${runId}`)
  },
}
