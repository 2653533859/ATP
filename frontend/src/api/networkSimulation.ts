import http from './http'

export interface NetworkProfile {
  name: string
  latency_ms: number
  download_kbps: number
  upload_kbps: number
  packet_loss_percent: number
  offline: boolean
  description?: string
}

export interface NetworkEvaluateRequest {
  profile_id: string
  payload_bytes?: number
  custom_profile?: Partial<NetworkProfile>
}

export interface NetworkEvaluateResponse {
  profile_id: string
  is_dropped: boolean
  estimated_delay_seconds: number
  offline: boolean
  cdp_conditions: Record<string, unknown>
  adb_commands: string[][]
}

export interface NetworkScheduleConfigResponse {
  profile_id: string
  setup_commands: string[][]
  teardown_commands: string[][]
  cdp_conditions: Record<string, unknown>
}

export interface HarEntry {
  index: number
  url: string
  method: string
  status: number
  duration_ms: number
  bytes: number
  is_failed: boolean
}

export interface HarParseResponse {
  valid: boolean
  total_requests: number
  failed_requests: number
  success_rate: number
  total_bytes_transferred: number
  avg_latency_ms: number
  domains_accessed: string[]
  slowest_requests: HarEntry[]
  entries_summary: HarEntry[]
  error?: string
}

export const networkSimulationApi = {
  getProfiles: () => http.get<unknown, Record<string, NetworkProfile>>('/network-profiles'),
  evaluate: (payload: NetworkEvaluateRequest) =>
    http.post<unknown, NetworkEvaluateResponse>('/network-profiles/evaluate', payload),
  getScheduleConfig: (payload: { profile_id: string; custom_profile?: Partial<NetworkProfile> }) =>
    http.post<unknown, NetworkScheduleConfigResponse>('/network-profiles/schedule-config', payload),
  parseHar: (harContent: string | Record<string, unknown>) =>
    http.post<unknown, HarParseResponse>('/network-profiles/parse-har', { har_content: harContent }),
}
