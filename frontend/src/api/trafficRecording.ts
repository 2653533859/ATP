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
}
