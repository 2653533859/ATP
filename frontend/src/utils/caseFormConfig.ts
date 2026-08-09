// CaseFormDrawer 的可测纯逻辑：编辑态回填时的配置解析，以及保存时的
// body / GraphQL 变量 / WebSocket 消息归一化。表单响应式状态留在组件层。

export function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === 'object' && value !== null && !Array.isArray(value)
}

export function asStringMap(value: unknown): Record<string, string> {
  return isRecord(value) ? { ...(value as Record<string, string>) } : {}
}

/** 用例 config 可能是 { steps: [...] } 或直接就是单步对象；取第一步。 */
export function getFirstStep(config: Record<string, unknown> | undefined): Record<string, unknown> {
  if (!config) return {}
  const steps = config.steps
  if (Array.isArray(steps) && isRecord(steps[0])) {
    return steps[0] as Record<string, unknown>
  }
  return config
}

/** 编辑态回填 form body：对象直接取，字符串尝试 JSON 解析，失败或其它类型给空。 */
export function parseFormBody(rawBody: unknown): Record<string, string> {
  if (isRecord(rawBody)) return asStringMap(rawBody)
  if (typeof rawBody === 'string' && rawBody.trim()) {
    try {
      return asStringMap(JSON.parse(rawBody))
    } catch {
      return {}
    }
  }
  return {}
}

/** 保存时解析请求体：json 且为字符串则尝试解析为对象，none 归一化为 null，其它原样。 */
export function resolveRequestBody(
  bodyType: 'none' | 'json' | 'form' | 'multipart' | 'xml' | 'raw',
  body: unknown,
  formBody: Record<string, string>,
): unknown {
  if (bodyType === 'none') return null
  if (bodyType === 'form') return { ...formBody }
  if (bodyType === 'json' && typeof body === 'string') {
    try {
      return JSON.parse(body)
    } catch {
      return body
    }
  }
  return body
}

/** GraphQL 变量文本 → 对象；空或非法 JSON 归一化为 {}。 */
export function parseGraphqlVariables(variablesText: string): unknown {
  if (!variablesText.trim()) return {}
  try {
    return JSON.parse(variablesText)
  } catch {
    return {}
  }
}

export interface WsMessageInput {
  action: string
  data?: string
  data_type?: string
  timeout?: number
  assertions?: unknown[]
  extractions?: unknown[]
}

/** WebSocket 消息按 action 归一化为落库形态：send 只留 data/data_type，receive 留 timeout+断言。 */
export function normalizeWsMessage(message: WsMessageInput): Record<string, unknown> {
  if (message.action === 'send') {
    return { action: 'send', data: message.data, data_type: message.data_type }
  }
  if (message.action === 'receive') {
    return {
      action: 'receive',
      timeout: message.timeout,
      assertions: message.assertions,
      extractions: message.extractions,
    }
  }
  return { action: message.action }
}
