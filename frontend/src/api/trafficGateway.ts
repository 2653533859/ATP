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
