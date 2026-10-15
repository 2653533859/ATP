import http from './http'

export interface RecordedTrafficEntry {
  method: string
  path: string
  status_code: number
  duration_ms: number
  captured_at: string
  is_noise_filtered: boolean
  headers?: Record<string, string>
  query_params?: Record<string, string>
  request_body?: Record<string, any> | string
  response_body?: Record<string, any> | string
}

export interface ParamDependency {
  producer_step: number
  consumer_step: number
  variable: string
  jsonpath: string
  matched_value: string
  location: 'url_path' | 'query_param' | 'header' | 'request_body'
}

export interface ExtractionRule {
  variable: string
  type: string
  expression: string
  description?: string
}

export interface ExtractParamsResponse {
  parameterized_entries: RecordedTrafficEntry[]
  discovered_dependencies: ParamDependency[]
  total_dependencies_count: number
}

export interface SynthesizeCaseRequest {
  case_name: string
  module_id: number
  description?: string
  priority?: string
  case_level?: string
  persist?: boolean
}

export interface SynthesizeCaseResponse {
  case_id: number | null
  name: string
  module_id: number
  project_id: number
  total_steps: number
  steps: Array<{
    step_no: number
    action: string
    test_data?: string
    expected_result?: string
    is_key_step?: boolean
  }>
  config: Record<string, any>
  dependencies_extracted: ParamDependency[]
  persisted: boolean
}

export interface SynthesizeSuiteRequest {
  suite_name: string
  module_id: number
  persist?: boolean
}

export interface SynthesizeSuiteResponse {
  suite_id: number | null
  suite_name: string
  case_id: number | null
  case_name: string
  project_id: number
  module_id: number
  total_steps: number
  persisted: boolean
}

export interface TrafficRecordingSession {
  session_id: string
  project_id: number
  target_base_url: string
  filter_noise: boolean
  is_recording: boolean
  created_at: string
  total_captured: number
  noise_filtered_ratio_pct: number
  recorded_entries: RecordedTrafficEntry[]
}

export interface StartTrafficRecordingRequest {
  project_id: number
  target_base_url: string
  filter_noise?: boolean
}

export interface IngestTrafficEntryRequest {
  method: string
  path: string
  status_code?: number
  duration_ms?: number
  headers?: Record<string, string>
  query_params?: Record<string, string>
  request_body?: Record<string, any> | string
  response_body?: Record<string, any> | string
}

export const trafficRecordingApi = {
  startSession(data: StartTrafficRecordingRequest): Promise<TrafficRecordingSession> {
    return http.post('/traffic-recording/sessions/start', data)
  },

  stopSession(sessionId: string): Promise<TrafficRecordingSession> {
    return http.post(`/traffic-recording/sessions/${sessionId}/stop`)
  },

  getSession(sessionId: string): Promise<TrafficRecordingSession> {
    return http.get(`/traffic-recording/sessions/${sessionId}`)
  },

  ingestEntry(sessionId: string, data: IngestTrafficEntryRequest): Promise<{ status: string; total_captured: number }> {
    return http.post(`/traffic-recording/sessions/${sessionId}/record`, data)
  },

  extractSessionParams(sessionId: string): Promise<ExtractParamsResponse> {
    return http.post(`/traffic-recording/sessions/${sessionId}/extract-params`)
  },

  extractParams(entries: RecordedTrafficEntry[]): Promise<ExtractParamsResponse> {
    return http.post('/traffic-recording/extract-params', { entries })
  },

  synthesizeCase(sessionId: string, data: SynthesizeCaseRequest): Promise<SynthesizeCaseResponse> {
    return http.post(`/traffic-recording/sessions/${sessionId}/synthesize-case`, data)
  },

  synthesizeSuite(sessionId: string, data: SynthesizeSuiteRequest): Promise<SynthesizeSuiteResponse> {
    return http.post(`/traffic-recording/sessions/${sessionId}/synthesize-suite`, data)
  },
}
