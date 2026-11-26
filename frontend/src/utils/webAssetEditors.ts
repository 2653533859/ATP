import { isPlainJsonObject } from './smartJson'

export const LOCATOR_STRATEGIES = [
  'css',
  'xpath',
  'role',
  'text',
  'testid',
  'label',
  'placeholder',
] as const

export const PAGE_ACTION_STEPS = [
  'click',
  'fill',
  'hover',
  'wait',
  'assert_text',
  'press',
  'select_option',
  'goto',
] as const

export interface WebLocatorRow {
  strategy: string
  value: string
  name: string
  exact: boolean
  extra?: Record<string, unknown>
}

export interface WebElementRefRow {
  asset_id: number | null
  alias: string
  extra?: Record<string, unknown>
}

export interface WebPageActionRow {
  name: string
  step: string
  alias: string
  value: string
  paramKey?: 'value' | 'text' | 'url'
  extra?: Record<string, unknown>
}

export interface WebIgnoreRegionRow {
  mode: 'selector' | 'box'
  selector: string
  x: number
  y: number
  width: number
  height: number
  extra?: Record<string, unknown>
}

function toLocatorRow(raw: Record<string, unknown>): WebLocatorRow {
  const { strategy, value, name, exact, ...rest } = raw
  return {
    strategy: typeof strategy === 'string' && strategy.trim() ? strategy : 'css',
    value: value == null ? '' : String(value),
    name: name == null ? '' : String(name),
    exact: Boolean(exact),
    extra: Object.keys(rest).length ? rest : undefined,
  }
}

function fromLocatorRow(row: WebLocatorRow): Record<string, unknown> {
  const out: Record<string, unknown> = { ...(row.extra || {}) }
  out.strategy = row.strategy || 'css'
  out.value = row.value
  if (row.name.trim()) out.name = row.name.trim()
  if (row.exact) out.exact = true
  return out
}

export function parseLocatorText(text: string): { valid: boolean; row: WebLocatorRow } {
  const fallback: WebLocatorRow = { strategy: 'css', value: '', name: '', exact: false }
  const trimmed = text.trim()
  if (!trimmed) return { valid: true, row: fallback }
  try {
    const parsed = JSON.parse(trimmed)
    if (!isPlainJsonObject(parsed)) return { valid: false, row: fallback }
    return { valid: true, row: toLocatorRow(parsed) }
  } catch {
    return { valid: false, row: fallback }
  }
}

export function serializeLocator(row: WebLocatorRow): string {
  return JSON.stringify(fromLocatorRow(row), null, 2)
}

export function parseFallbackLocatorsText(text: string): { valid: boolean; rows: WebLocatorRow[] } {
  const trimmed = text.trim()
  if (!trimmed) return { valid: true, rows: [] }
  try {
    const parsed = JSON.parse(trimmed)
    if (!Array.isArray(parsed) || !parsed.every(isPlainJsonObject)) return { valid: false, rows: [] }
    return { valid: true, rows: parsed.map(toLocatorRow) }
  } catch {
    return { valid: false, rows: [] }
  }
}

export function serializeFallbackLocators(rows: readonly WebLocatorRow[]): string {
  return JSON.stringify(
    rows.filter((row) => row.value.trim() || row.name.trim()).map(fromLocatorRow),
    null,
    2,
  )
}

export function parseElementRefsText(text: string): { valid: boolean; rows: WebElementRefRow[] } {
  const trimmed = text.trim()
  if (!trimmed) return { valid: true, rows: [] }
  try {
    const parsed = JSON.parse(trimmed)
    if (!Array.isArray(parsed) || !parsed.every(isPlainJsonObject)) return { valid: false, rows: [] }
    return {
      valid: true,
      rows: parsed.map(({ asset_id, alias, ...rest }) => ({
        asset_id: typeof asset_id === 'number' && Number.isFinite(asset_id) ? asset_id : null,
        alias: alias == null ? '' : String(alias),
        extra: Object.keys(rest).length ? rest : undefined,
      })),
    }
  } catch {
    return { valid: false, rows: [] }
  }
}

export function serializeElementRefs(rows: readonly WebElementRefRow[]): string {
  return JSON.stringify(
    rows
      .filter((row) => row.asset_id != null || row.alias.trim())
      .map((row) => ({
        ...(row.extra || {}),
        ...(row.asset_id != null ? { asset_id: row.asset_id } : {}),
        alias: row.alias.trim(),
      })),
    null,
    2,
  )
}

export function parsePageActionsText(text: string): { valid: boolean; rows: WebPageActionRow[] } {
  const trimmed = text.trim()
  if (!trimmed) return { valid: true, rows: [] }
  try {
    const parsed = JSON.parse(trimmed)
    if (!Array.isArray(parsed) || !parsed.every(isPlainJsonObject)) return { valid: false, rows: [] }
    return {
      valid: true,
      rows: parsed.map(({ name, step, alias, value, target, ...rest }) => {
        const paramsObj = isPlainJsonObject(rest.params) ? rest.params : undefined
        let resolvedValue = value == null ? '' : String(value)
        let paramKey: WebPageActionRow['paramKey']
        if (value == null && paramsObj) {
          if (paramsObj.value != null) {
            resolvedValue = String(paramsObj.value)
            paramKey = 'value'
          } else if (paramsObj.text != null) {
            resolvedValue = String(paramsObj.text)
            paramKey = 'text'
          } else if (paramsObj.url != null) {
            resolvedValue = String(paramsObj.url)
            paramKey = 'url'
          }
        }
        return {
          name: name == null ? '' : String(name),
          step: typeof step === 'string' && step.trim() ? step : 'click',
          alias: alias != null ? String(alias) : target != null ? String(target) : '',
          value: resolvedValue,
          paramKey,
          extra: Object.keys(rest).length ? rest : undefined,
        }
      }),
    }
  } catch {
    return { valid: false, rows: [] }
  }
}

export function serializePageActions(rows: readonly WebPageActionRow[]): string {
  return JSON.stringify(
    rows
      .filter((row) => row.name.trim() || row.alias.trim() || row.value.trim())
      .map((row) => {
        const out: Record<string, unknown> = { ...(row.extra || {}) }
        out.name = row.name.trim()
        out.step = row.step.trim() || 'click'
        if (row.alias.trim()) out.alias = row.alias.trim()
        if (row.paramKey && isPlainJsonObject(out.params)) {
          const nextParams: Record<string, unknown> = { ...out.params }
          if (row.value.trim()) nextParams[row.paramKey] = row.value
          else delete nextParams[row.paramKey]
          out.params = nextParams
        } else if (row.value.trim()) {
          out.value = row.value
        }
        return out
      }),
    null,
    2,
  )
}

export function parseIgnoreRegionsText(text: string): { valid: boolean; rows: WebIgnoreRegionRow[] } {
  const trimmed = text.trim()
  if (!trimmed) return { valid: true, rows: [] }
  try {
    const parsed = JSON.parse(trimmed)
    if (!Array.isArray(parsed) || !parsed.every(isPlainJsonObject)) return { valid: false, rows: [] }
    return {
      valid: true,
      rows: parsed.map(({ selector, x, y, width, height, ...rest }) => {
        const hasSelector = typeof selector === 'string' && Boolean(selector.trim())
        return {
          mode: hasSelector || (x == null && y == null && width == null && height == null) ? 'selector' : 'box',
          selector: typeof selector === 'string' ? selector : '',
          x: Number(x || 0),
          y: Number(y || 0),
          width: Number(width || 0),
          height: Number(height || 0),
          extra: Object.keys(rest).length ? rest : undefined,
        }
      }),
    }
  } catch {
    return { valid: false, rows: [] }
  }
}

export function serializeIgnoreRegions(rows: readonly WebIgnoreRegionRow[]): string {
  return JSON.stringify(
    rows.map((row) => {
      const out: Record<string, unknown> = { ...(row.extra || {}) }
      if (row.mode === 'selector') {
        out.selector = row.selector.trim()
      } else {
        out.x = Number(row.x || 0)
        out.y = Number(row.y || 0)
        out.width = Number(row.width || 0)
        out.height = Number(row.height || 0)
      }
      return out
    }),
    null,
    2,
  )
}
