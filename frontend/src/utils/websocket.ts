/**
 * WebSocket 连接封装
 * 自动处理重连（最多 3 次）、消息解析
 */
export type WsMessage = {
  type:
    | 'run_status'
    | 'step_result'
    | 'completed'
    | 'healing_suggestion'
    | 'run_healing_suggestion'
    | 'started'
    | 'phase'
    | 'progress'
    | 'sampling'
    | 'incident'
    | 'log'
    | 'stage_start'
    | 'stage_end'
  run_id: number
  status?: string
  duration_ms?: number
  video_url?: string
  phase?: string
  progress?: number
  current_step?: string
  sample_count?: number
  samples?: number
  elapsed_seconds?: number
  duration_seconds?: number
  device_serial?: string | null
  device_status?: 'online' | 'offline' | 'pending' | 'unknown' | string
  sample_metrics?: Array<{
    metric_type: string
    metric_value: number
    sample_time?: string
  }>
  incident_type?: string
  incident_count?: number
  title?: string
  detail?: string
  message?: string
  level?: 'debug' | 'info' | 'warning' | 'error' | string
  error?: string | null
  summary?: Record<string, unknown>
  stage_index?: number
  stage_name?: string
  step?: {
    step_index: number
    name: string
    status: string
    duration_ms: number | null
    request_data: Record<string, unknown> | null
    response_data: Record<string, unknown> | null
    error_message: string | null
    screenshot_url: string | null
    healing_suggestion?: string | null
    healing_status?: string | null
    healing_at?: string | null
  }
  // healing_suggestion / run_healing_suggestion 消息专用字段
  step_id?: number
  step_index?: number
  suggestion?: string | null
  cache_hit?: boolean
}

type MessageHandler = (msg: WsMessage) => void
type CloseHandler = () => void

export function createRunWebSocket(
  runId: number,
  onMessage: MessageHandler,
  onClose?: CloseHandler,
  runType: 'case' | 'mobile' = 'case',
) {
  const protocol = location.protocol === 'https:' ? 'wss:' : 'ws:'
  // Use the page origin so the browser sends the host-only HttpOnly Cookie.
  // Vite proxies /ws to the backend during local development.
  const query = runType === 'mobile' ? '?run_type=mobile' : ''
  const baseUrl = `${protocol}//${location.host}/ws/runs/${runId}${query}`

  let ws: WebSocket | null = null
  let retries = 0
  const MAX_RETRIES = 3

  function connect() {
    // WebSocket 会自动携带同源 HttpOnly Cookie，避免 JWT 出现在 URL、历史记录或代理日志中。
    ws = new WebSocket(baseUrl)

    ws.onmessage = (e) => {
      try {
        const msg: WsMessage = JSON.parse(e.data)
        onMessage(msg)
      } catch {
        // 忽略非 JSON 消息
      }
    }

    ws.onerror = () => {
      // error 之后会触发 onclose，统一在 onclose 处理重连
    }

    ws.onclose = (e) => {
      if (e.code === 1000) {
        // 正常关闭
        onClose?.()
        return
      }
      if (retries < MAX_RETRIES) {
        retries++
        setTimeout(connect, 1000 * retries)
      } else {
        onClose?.()
      }
    }
  }

  connect()

  return {
    close: () => {
      retries = MAX_RETRIES  // 禁止重连
      ws?.close(1000)
    },
  }
}
