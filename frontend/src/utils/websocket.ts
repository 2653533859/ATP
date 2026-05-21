/**
 * WebSocket 连接封装
 * 自动处理重连（最多 3 次）、消息解析
 */
export type WsMessage = {
  type: 'run_status' | 'step_result' | 'completed' | 'healing_suggestion' | 'run_healing_suggestion'
  run_id: number
  status?: string
  duration_ms?: number
  video_url?: string
  step?: {
    step_index: number
    name: string
    status: string
    duration_ms: number | null
    request_data: Record<string, any> | null
    response_data: Record<string, any> | null
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

export function createRunWebSocket(runId: number, onMessage: MessageHandler, onClose?: CloseHandler) {
  const protocol = location.protocol === 'https:' ? 'wss:' : 'ws:'
  const host = import.meta.env.DEV ? 'localhost:8000' : location.host
  const baseUrl = `${protocol}//${host}/ws/runs/${runId}`

  let ws: WebSocket | null = null
  let retries = 0
  const MAX_RETRIES = 3

  function connect() {
    const token = localStorage.getItem('access_token')
    const url = token ? `${baseUrl}?token=${encodeURIComponent(token)}` : baseUrl
    ws = new WebSocket(url)

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
