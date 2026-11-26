import { isPlainJsonObject } from './smartJson'

export type FluencyActionType = 'swipe' | 'tap'

export interface FluencyStageRow {
  name: string
  action: FluencyActionType
  duration_seconds: number
  x1: number
  y1: number
  x2: number
  y2: number
  x: number
  y: number
  extra?: Record<string, unknown>
}

export function parseFluencyStagesText(text: string): { valid: boolean; rows: FluencyStageRow[] } {
  const trimmed = text.trim()
  if (!trimmed) return { valid: true, rows: [] }
  try {
    const parsed = JSON.parse(trimmed)
    if (!Array.isArray(parsed) || !parsed.every(isPlainJsonObject)) {
      return { valid: false, rows: [] }
    }
    const rows: FluencyStageRow[] = parsed.map((stage, idx) => {
      const { name, action, duration_seconds, coords, ...rest } = stage
      const normalizedAction: FluencyActionType = action === 'tap' ? 'tap' : 'swipe'
      const c = isPlainJsonObject(coords) ? coords : {}
      return {
        name: typeof name === 'string' ? name : `stage_${idx + 1}`,
        action: normalizedAction,
        duration_seconds: Number(duration_seconds ?? 5),
        x1: Number(c.x1 ?? 540),
        y1: Number(c.y1 ?? 1400),
        x2: Number(c.x2 ?? 540),
        y2: Number(c.y2 ?? 400),
        x: Number(c.x ?? 540),
        y: Number(c.y ?? 1000),
        extra: Object.keys(rest).length ? rest : undefined,
      }
    })
    return { valid: true, rows }
  } catch {
    return { valid: false, rows: [] }
  }
}

export function serializeFluencyStages(rows: readonly FluencyStageRow[]): string {
  if (!rows.length) return ''
  const payload = rows.map((row) => {
    const coords = row.action === 'tap'
      ? { x: Number(row.x || 0), y: Number(row.y || 0) }
      : {
          x1: Number(row.x1 || 0),
          y1: Number(row.y1 || 0),
          x2: Number(row.x2 || 0),
          y2: Number(row.y2 || 0),
        }
    return {
      ...(row.extra || {}),
      name: row.name.trim() || 'stage',
      action: row.action,
      coords,
      duration_seconds: Number.isFinite(Number(row.duration_seconds)) && Number(row.duration_seconds) > 0
        ? Number(row.duration_seconds)
        : 5,
    }
  })
  return JSON.stringify(payload, null, 2)
}
