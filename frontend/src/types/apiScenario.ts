import type { CaseDetailItem } from '@/api'

export interface ApiAssertionItem {
  target: string
  operator: string
  expected?: string
  expression?: string
  description?: string
  schema_asset_id?: number
  [key: string]: unknown
}

export interface ApiExtractionItem {
  variable: string
  type?: 'jsonpath' | 'xpath' | 'regex' | 'header'
  expression: string
  description?: string
  [key: string]: unknown
}

export interface ApiScenarioStep {
  name?: string
  method?: string
  url?: string
  headers?: Record<string, string>
  params?: Record<string, string>
  cookies?: Record<string, string>
  body_type?: 'none' | 'json' | 'form' | 'multipart' | 'xml' | 'raw'
  body?: unknown
  assertions?: ApiAssertionItem[]
  extractions?: ApiExtractionItem[]
  depends_on?: number[]
  timeout?: number
  response_type?: string
  [key: string]: unknown
}

export function parseStepFromCase(caseItem: CaseDetailItem | Record<string, unknown>): ApiScenarioStep {
  const config = (caseItem.config || {}) as Record<string, unknown>
  const rawSteps = Array.isArray(config.steps) ? config.steps : []
  const firstStep = (rawSteps[0] || {}) as Record<string, unknown>

  const name = String(caseItem.name || firstStep.name || 'API 步骤')
  const method = String(firstStep.method || config.method || 'GET').toUpperCase()
  const url = String(firstStep.url || config.url || firstStep.endpoint || config.endpoint || '')
  const headers = (firstStep.headers || config.headers || {}) as Record<string, string>
  const params = (firstStep.params || config.params || {}) as Record<string, string>
  const cookies = (firstStep.cookies || config.cookies || {}) as Record<string, string>
  const body_type = (firstStep.body_type || config.body_type || 'none') as ApiScenarioStep['body_type']
  const body = firstStep.body ?? config.body ?? ''
  const assertions = (Array.isArray(firstStep.assertions)
    ? firstStep.assertions
    : Array.isArray(config.assertions)
      ? config.assertions
      : []) as ApiAssertionItem[]
  const extractions = (Array.isArray(firstStep.extractions)
    ? firstStep.extractions
    : Array.isArray(config.extractions)
      ? config.extractions
      : []) as ApiExtractionItem[]

  return {
    name,
    method,
    url,
    headers: { ...headers },
    params: { ...params },
    cookies: { ...cookies },
    body_type,
    body,
    assertions: [...assertions],
    extractions: [...extractions],
    depends_on: [],
  }
}

const VAR_REGEX = /\{\{([a-zA-Z0-9_\-\.]+)\}\}/g

export function detectVariableReferences(step: ApiScenarioStep): string[] {
  const vars = new Set<string>()

  function scanText(text: unknown) {
    if (typeof text !== 'string') return
    let match: RegExpExecArray | null
    const regex = new RegExp(VAR_REGEX.source, 'g')
    while ((match = regex.exec(text)) !== null) {
      if (match[1]) vars.add(match[1].trim())
    }
  }

  scanText(step.url)
  if (step.headers && typeof step.headers === 'object') {
    Object.values(step.headers).forEach(scanText)
  }
  if (step.params && typeof step.params === 'object') {
    Object.values(step.params).forEach(scanText)
  }
  if (typeof step.body === 'string') {
    scanText(step.body)
  } else if (step.body && typeof step.body === 'object') {
    try {
      scanText(JSON.stringify(step.body))
    } catch {
      // ignore
    }
  }

  return Array.from(vars)
}

export function detectVariableExtractions(step: ApiScenarioStep): string[] {
  if (!Array.isArray(step.extractions)) return []
  return step.extractions
    .map((e) => e.variable?.trim())
    .filter((v): v is string => Boolean(v))
}
