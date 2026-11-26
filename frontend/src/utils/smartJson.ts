export type JsonFieldType = 'string' | 'number' | 'boolean' | 'null' | 'json'

export interface JsonFieldRow {
  key: string
  type: JsonFieldType
  value: string
}

export type JsonVisualBlockerReason = 'invalid' | 'array' | 'primitive' | 'template'

export interface JsonValidationResult {
  valid: boolean
  empty: boolean
  canUseVisual: boolean
  reason?: JsonVisualBlockerReason
  error?: string
}

export interface JsonTemplateOption {
  id: string
  label: string
  preview: string
  value: string
}

export const HEADER_KEY_SUGGESTIONS = [
  'Content-Type',
  'Authorization',
  'Accept',
  'X-Request-Id',
  'X-Env',
  'User-Agent',
  'Cache-Control',
] as const

export const API_BODY_TEMPLATES: readonly JsonTemplateOption[] = [
  {
    id: 'empty_object',
    label: '空 JSON 对象',
    preview: '{}',
    value: '{}',
  },
  {
    id: 'pagination',
    label: '分页检索参数',
    preview: '{"page": 1, "page_size": 20, "keyword": ""}',
    value: JSON.stringify({ page: 1, page_size: 20, keyword: '' }, null, 2),
  },
  {
    id: 'login_credentials',
    label: '登录凭证结构',
    preview: '{"username": "admin", "password": "password"}',
    value: JSON.stringify({ username: 'admin', password: 'password' }, null, 2),
  },
  {
    id: 'id_update',
    label: '状态更新模板',
    preview: '{"id": "{{id}}", "status": "active"}',
    value: JSON.stringify({ id: '{{id}}', status: 'active' }, null, 2),
  },
  {
    id: 'object_array',
    label: '对象数组结构',
    preview: '[{"name": "item1"}]',
    value: JSON.stringify([{ name: 'item1' }], null, 2),
  },
]

export const MOCK_BODY_TEMPLATES: readonly JsonTemplateOption[] = [
  {
    id: 'mock_success',
    label: '标准成功响应',
    preview: '{"code": 0, "message": "success", "data": {}}',
    value: JSON.stringify({ code: 0, message: 'success', data: {} }, null, 2),
  },
  {
    id: 'mock_page',
    label: '分页列表响应',
    preview: '{"code": 0, "data": {"items": [], "total": 0}}',
    value: JSON.stringify({ code: 0, data: { items: [], total: 0 } }, null, 2),
  },
  {
    id: 'mock_error',
    label: '业务错误响应',
    preview: '{"code": 40001, "message": "invalid parameter"}',
    value: JSON.stringify({ code: 40001, message: 'invalid parameter' }, null, 2),
  },
]

export const BUG_TRACKER_MAPPING_TEMPLATES: readonly JsonTemplateOption[] = [
  {
    id: 'jira_default',
    label: 'Jira 标准映射',
    preview: '{"priority": "High", "labels": ["automation"], "components": ["QA"]}',
    value: JSON.stringify({ priority: 'High', labels: ['automation'], components: ['QA'], custom_fields: {} }, null, 2),
  },
  {
    id: 'git_labels',
    label: 'GitHub / GitLab 标签映射',
    preview: '{"labels": ["bug", "automated-test"]}',
    value: JSON.stringify({ labels: ['bug', 'automated-test'] }, null, 2),
  },
  {
    id: 'empty_mapping',
    label: '空映射',
    preview: '{}',
    value: '{}',
  },
]

export const LLM_PARAMS_TEMPLATES: readonly JsonTemplateOption[] = [
  {
    id: 'llm_precise',
    label: '精准稳定（低温度）',
    preview: '{"temperature": 0.2}',
    value: JSON.stringify({ temperature: 0.2 }, null, 2),
  },
  {
    id: 'llm_balanced',
    label: '均衡默认',
    preview: '{"temperature": 0.4}',
    value: JSON.stringify({ temperature: 0.4 }, null, 2),
  },
  {
    id: 'llm_long_output',
    label: '长输出扩展',
    preview: '{"temperature": 0.3, "max_tokens": 4096}',
    value: JSON.stringify({ temperature: 0.3, max_tokens: 4096 }, null, 2),
  },
]

const UNQUOTED_TEMPLATE_RE = /([{[,:\s])\{\{[^}]+\}\}(?=\s*[,}\]])/

function sanitizeTemplatePlaceholders(raw: string): string {
  return raw.replace(/([{[,:\s])(\{\{[^}]+\}\})(?=\s*[,}\]])/g, '$1"__tpl__"')
}

export function isPlainJsonObject(value: unknown): value is Record<string, unknown> {
  return Boolean(value) && typeof value === 'object' && !Array.isArray(value)
}

export function validateJsonText(text: string, allowTemplates = false): JsonValidationResult {
  const trimmed = text.trim()
  if (!trimmed) {
    return { valid: true, empty: true, canUseVisual: true }
  }

  const hasUnquotedTemplate = allowTemplates && UNQUOTED_TEMPLATE_RE.test(trimmed)
  try {
    const parsed = JSON.parse(hasUnquotedTemplate ? sanitizeTemplatePlaceholders(trimmed) : trimmed)
    if (Array.isArray(parsed)) {
      return { valid: true, empty: false, canUseVisual: false, reason: 'array' }
    }
    if (!isPlainJsonObject(parsed)) {
      return { valid: true, empty: false, canUseVisual: false, reason: 'primitive' }
    }
    if (hasUnquotedTemplate) {
      return { valid: true, empty: false, canUseVisual: false, reason: 'template' }
    }
    return { valid: true, empty: false, canUseVisual: true }
  } catch (err) {
    return {
      valid: false,
      empty: false,
      canUseVisual: false,
      reason: 'invalid',
      error: err instanceof Error ? err.message : String(err),
    }
  }
}

export function inferJsonFieldType(value: unknown): JsonFieldType {
  if (value === null) return 'null'
  if (typeof value === 'number') return 'number'
  if (typeof value === 'boolean') return 'boolean'
  if (typeof value === 'object') return 'json'
  return 'string'
}

export function jsonTextToRows(text: string): JsonFieldRow[] | null {
  const trimmed = text.trim()
  if (!trimmed) return []
  try {
    const parsed = JSON.parse(trimmed)
    if (!isPlainJsonObject(parsed)) return null
    return Object.entries(parsed).map(([key, val]) => {
      const type = inferJsonFieldType(val)
      let valueText = ''
      if (type === 'null') valueText = ''
      else if (type === 'json') valueText = JSON.stringify(val)
      else valueText = String(val)
      return { key, type, value: valueText }
    })
  } catch {
    return null
  }
}

export function parseRowValue(row: JsonFieldRow): unknown {
  if (row.type === 'null') return null
  if (row.type === 'boolean') return row.value.trim().toLowerCase() === 'true'
  if (row.type === 'number') {
    const trimmed = row.value.trim()
    if (!trimmed) return 0
    const parsed = Number(trimmed)
    return Number.isFinite(parsed) ? parsed : row.value
  }
  if (row.type === 'json') {
    const trimmed = row.value.trim()
    if (!trimmed) return {}
    try {
      return JSON.parse(trimmed)
    } catch {
      return row.value
    }
  }
  return row.value
}

export function rowsToJsonText(rows: readonly JsonFieldRow[], indent = 2): string {
  const output: Record<string, unknown> = {}
  let count = 0
  for (const row of rows) {
    const key = row.key.trim()
    if (!key) continue
    output[key] = parseRowValue(row)
    count += 1
  }
  if (!count) return '{}'
  return JSON.stringify(output, null, indent)
}
