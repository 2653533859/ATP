import { isPlainJsonObject } from './smartJson'

export type FixtureActionKind = 'set_variable' | 'delete_variable' | 'request'

export interface FixtureActionRow {
  action: FixtureActionKind
  variable: string
  value: string
  method: string
  url: string
  extra?: Record<string, unknown>
}

export function parseFixtureActionsText(text: string): { valid: boolean; rows: FixtureActionRow[] } {
  const trimmed = text.trim()
  if (!trimmed) return { valid: true, rows: [] }
  try {
    const parsed = JSON.parse(trimmed)
    if (!Array.isArray(parsed) || !parsed.every(isPlainJsonObject)) {
      return { valid: false, rows: [] }
    }
    const rows: FixtureActionRow[] = []
    for (const item of parsed) {
      const { action, variable, value, method, url, ...rest } = item
      const rawAction = typeof action === 'string' ? action.trim() : 'set_variable'
      if (rawAction !== 'set_variable' && rawAction !== 'delete_variable' && rawAction !== 'request') {
        return { valid: false, rows: [] }
      }
      rows.push({
        action: rawAction,
        variable: variable == null ? '' : String(variable),
        value: value == null ? '' : typeof value === 'string' ? value : JSON.stringify(value),
        method: typeof method === 'string' && method.trim() ? method.toUpperCase() : 'GET',
        url: url == null ? '' : String(url),
        extra: Object.keys(rest).length ? rest : undefined,
      })
    }
    return { valid: true, rows }
  } catch {
    return { valid: false, rows: [] }
  }
}

export function serializeFixtureActions(rows: readonly FixtureActionRow[]): string {
  const output = rows
    .filter((row) => {
      if (row.action === 'request') return Boolean(row.url.trim())
      return Boolean(row.variable.trim())
    })
    .map((row) => {
      const item: Record<string, unknown> = { ...(row.extra || {}), action: row.action }
      if (row.action === 'set_variable') {
        item.variable = row.variable.trim()
        item.value = row.value
      } else if (row.action === 'delete_variable') {
        item.variable = row.variable.trim()
      } else {
        item.method = row.method || 'GET'
        item.url = row.url.trim()
      }
      return item
    })
  return JSON.stringify(output, null, 2)
}
