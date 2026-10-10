import { useAuthStore } from '@/stores/auth'

export interface AiChatStreamPayload {
  query: string
  project_id?: number
  history?: Array<{ role: 'user' | 'assistant'; content: string }>
}

export async function streamAiChat(
  payload: AiChatStreamPayload,
  onToken: (token: string) => void,
  signal?: AbortSignal
): Promise<string> {
  const auth = useAuthStore()
  const headers: Record<string, string> = {
    'Content-Type': 'application/json',
    'X-Requested-With': 'XMLHttpRequest',
  }
  if (auth.token) {
    headers['Authorization'] = `Bearer ${auth.token}`
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
        const parsed = JSON.parse(dataStr) as { token?: string; error?: string }
        if (parsed.error) {
          throw new Error(parsed.error)
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
