import http from './http'

export interface PerformanceSamplePoint {
  timestamp_sec: number
  cpu_app_pct: number
  cpu_total_pct: number
  memory_pss_mb: number
  memory_native_heap_mb: number
  memory_dalvik_heap_mb: number
  fps: number
  jank_count: number
  net_tx_kbps: number
  net_rx_kbps: number
}

export type AnomalyType = 'MEMORY_LEAK_WARNING' | 'HIGH_CPU_ALERT' | 'JANK_FRAME_DROP'
export type AnomalySeverity = 'critical' | 'warning' | 'info'

export interface DiagnosticAnomaly {
  anomaly_type: AnomalyType
  severity: AnomalySeverity
  timestamp_sec: number
  metric_name: string
  metric_value: number
  threshold: number
  description: string
}

export interface MobilePerfSummary {
  cpu_app_avg: number
  cpu_app_max: number
  memory_pss_max: number
  memory_growth_slope_mb_per_min: number
  fps_avg: number
  total_janks: number
  anomalies_count: number
  has_memory_leak: boolean
  has_jank_drops: boolean
  empty?: boolean
}

export interface MobilePerfSessionReport {
  session_id: string
  device_serial: string
  package_name: string
  started_at: string
  ended_at: string | null
  total_samples_count: number
  summary: MobilePerfSummary
  anomalies: DiagnosticAnomaly[]
  samples_preview: PerformanceSamplePoint[]
}

export interface StartPerfSessionRequest {
  session_id: string
  device_serial: string
  package_name: string
  sample_interval_sec?: number
}

export const mobilePerfApi = {
  startSession(data: StartPerfSessionRequest): Promise<{ message: string; session: MobilePerfSessionReport }> {
    return http.post('/diagnostics/mobile-perf/sessions/start', data)
  },

  appendSamples(sessionId: string, samples: PerformanceSamplePoint[]): Promise<{ message: string; session_id: string }> {
    return http.post(`/diagnostics/mobile-perf/sessions/${sessionId}/samples`, { samples })
  },

  stopSession(sessionId: string): Promise<{ message: string; report: MobilePerfSessionReport }> {
    return http.post(`/diagnostics/mobile-perf/sessions/${sessionId}/stop`)
  },

  listSessions(): Promise<{ total: number; sessions: MobilePerfSessionReport[] }> {
    return http.get('/diagnostics/mobile-perf/sessions')
  },

  getSession(sessionId: string): Promise<MobilePerfSessionReport> {
    return http.get(`/diagnostics/mobile-perf/sessions/${sessionId}`)
  },
}
