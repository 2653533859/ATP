import http from './http'

export interface PlaybackStepRecord {
  step_no: number
  action: string
  params: Record<string, any>
  status: 'passed' | 'failed' | 'healed'
  duration_ms: number
  healed: boolean
  healing_technique?: string
  error_message?: string
}

export interface PlaybackSessionSummary {
  session_id: string
  platform: 'android' | 'ios'
  device_id: number
  serial_or_udid: string
  target_app: string
  status: 'idle' | 'running' | 'teardown'
  created_at: string
  total_steps: number
  passed_steps: number
  failed_steps: number
  healed_steps: number
  step_records: PlaybackStepRecord[]
}

export interface InitPlaybackSessionRequest {
  platform?: string
  device_id: number
  serial_or_udid: string
  target_app: string
}

export interface ExecutePlaybackStepRequest {
  step_no: number
  step_dict: {
    action: string
    params: Record<string, any>
  }
}

export const devicePlaybackApi = {
  initSession(data: InitPlaybackSessionRequest): Promise<PlaybackSessionSummary> {
    return http.post('/device-playback/sessions/init', data)
  },

  executeStep(sessionId: string, data: ExecutePlaybackStepRequest): Promise<PlaybackStepRecord> {
    return http.post(`/device-playback/sessions/${sessionId}/execute-step`, data)
  },

  teardownSession(sessionId: string): Promise<PlaybackSessionSummary> {
    return http.post(`/device-playback/sessions/${sessionId}/teardown`)
  },

  getSession(sessionId: string): Promise<PlaybackSessionSummary> {
    return http.get(`/device-playback/sessions/${sessionId}`)
  },
}
