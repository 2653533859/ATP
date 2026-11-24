import http from '@/api/http'
import { getRuntimeMode } from '@/runtimeMode'

export interface AiChatToolEvent {
  tool: string
  label: string
  summary: string
}

export type ChatActionType =
  | 'run_case'
  | 'run_suite'
  | 'create_case'
  | 'update_case'
  | 'create_defect'
  | 'update_defect'
  | 'create_knowledge'

export interface AiChatActionProposal {
  action: ChatActionType
  title: string
  summary: string
  params: Record<string, unknown>
  status?: 'pending' | 'executing' | 'executed' | 'cancelled' | 'failed'
  resultMessage?: string
  resultRoute?: string
}

export interface AiChatStreamPayload {
  query: string
  project_id?: number
  history?: Array<{ role: 'user' | 'assistant'; content: string }>
}

export interface AiChatStreamCallbacks {
  onToolEvent?: (event: AiChatToolEvent) => void
  onActionProposal?: (proposal: AiChatActionProposal) => void
}

export async function executeAiChatAction(data: {
  project_id: number
  action: ChatActionType
  params: Record<string, unknown>
}) {
  return http.post<
    unknown,
    {
      ok: boolean
      action: ChatActionType
      message: string
      resource_id?: number | null
      route?: string | null
    }
  >('/ai/chat/execute-action', data)
}

export async function streamAiChat(
  payload: AiChatStreamPayload,
  onToken: (token: string) => void,
  signal?: AbortSignal,
  callbacks?: AiChatStreamCallbacks,
): Promise<string> {
  const headers: Record<string, string> = {
    'Content-Type': 'application/json',
    'X-Requested-With': 'XMLHttpRequest',
    'X-ATP-Client-Mode': getRuntimeMode()?.mode || (import.meta.env.VITE_ATP_LOCAL_MODE === 'true' ? 'local' : 'server'),
  }

  const response = await fetch('/api/v1/ai/chat/stream', {
    method: 'POST',
    headers,
    credentials: 'include',
    body: JSON.stringify(payload),
    signal,
  })

  if (!response.ok) {
    const errorText = await response.text()
    throw new Error(errorText || `请求失败 (HTTP ${response.status})`)
  }

  const reader = response.body?.getReader()
  if (!reader) throw new Error('流式读取器不可用')

  const decoder = new TextDecoder()
  let fullText = ''
  let buffer = ''

  while (true) {
    const { done, value } = await reader.read()
    if (done) break
    buffer += decoder.decode(value, { stream: true })
    const lines = buffer.split('\n')
    buffer = lines.pop() || ''

    for (const line of lines) {
      const trimmed = line.trim()
      if (!trimmed || !trimmed.startsWith('data: ')) continue
      const dataStr = trimmed.slice(6)
      if (dataStr === '[DONE]') break
      try {
        const parsed = JSON.parse(dataStr) as {
          token?: string
          error?: string
          tool_event?: AiChatToolEvent
          action_proposal?: AiChatActionProposal
        }
        if (parsed.error) {
          throw new Error(parsed.error)
        }
        if (parsed.tool_event) {
          callbacks?.onToolEvent?.(parsed.tool_event)
        }
        if (parsed.action_proposal) {
          callbacks?.onActionProposal?.(parsed.action_proposal)
        }
        if (parsed.token) {
          fullText += parsed.token
          onToken(parsed.token)
        }
      } catch (err: unknown) {
        if (err instanceof Error && err.message !== dataStr) {
          throw err
        }
      }
    }
  }

  return fullText
}
