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

export interface HybridLocateRequest {
  target_params: Record<string, any>
  ax_elements?: Array<Record<string, any>>
  ocr_blocks?: Array<{
    text: string
    bounds?: [number, number, number, number] | string | number[]
    confidence?: number
  }>
}

export interface HybridLocateResponse {
  success: boolean
  matched_strategy: 'exact_dom' | 'fuzzy_ax_tree' | 'visual_ocr' | 'none'
  confidence_score: number
  healed: boolean
  click_coordinates: [number, number] | null
  target_element: Record<string, any> | null
  healing_details: string | null
}

export interface AlignedStepTimelineItem {
  step_no: number
  action: string
  params: Record<string, any>
  status: string
  duration_ms: number
  video_start_sec: number
  video_end_sec: number
  keyframe_frame: number
  is_keyframe: boolean
  highlight_type: 'normal' | 'self_healed' | 'failure'
  highlight_color: string
  error_message?: string | null
  screenshot_url?: string | null
  healing_details?: string | null
}

export interface SeekMarker {
  step_no: number
  timestamp_sec: number
  frame: number
  type: string
  color: string
  error_message?: string | null
}

export interface PlaybackTimelineReport {
  report_id: string
  session_id: string
  platform: string
  generated_at: string
  video_summary: {
    video_url: string
    duration_seconds: number
    fps: number
    total_frames: number
  }
  execution_summary: {
    total_steps: number
    passed_steps: number
    failed_steps: number
    healed_steps: number
    success_rate: number
    overall_status: string
  }
  timeline: AlignedStepTimelineItem[]
  seek_markers: SeekMarker[]
}

export interface CompileSessionReportRequest {
  video_url?: string
  video_duration_seconds?: number
}

export interface CompileRawReportRequest {
  session_id: string
  platform?: string
  step_records: Array<Record<string, any>>
  video_url?: string
  video_start_time?: string
  video_duration_seconds?: number
  fps?: number
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

  hybridLocate(data: HybridLocateRequest): Promise<HybridLocateResponse> {
    return http.post('/device-playback/hybrid-locate', data)
  },

  compileSessionTimelineReport(
    sessionId: string,
    data?: CompileSessionReportRequest
  ): Promise<PlaybackTimelineReport> {
    return http.post(`/device-playback/sessions/${sessionId}/timeline-report`, data || {})
  },

  compileRawTimelineReport(data: CompileRawReportRequest): Promise<PlaybackTimelineReport> {
    return http.post('/device-playback/timeline-report/compile', data)
  },
}
