import type { PerformanceSummary } from '@/api'

export interface PerformanceThresholdRow {
  key: string
  metric: string
  rule: string
  ok: boolean
}

export type PerformanceThresholdGateStatus = 'passed' | 'failed' | 'not_configured'

export interface PerformanceThresholdGate {
  status: PerformanceThresholdGateStatus
  total: number
  passed: number
  failed: number
}

export function getPerformanceThresholdRows(summary?: PerformanceSummary | null): PerformanceThresholdRow[] {
  const thresholds = summary?.thresholds
  if (!thresholds || typeof thresholds !== 'object' || Array.isArray(thresholds)) {
    return []
  }

  const rows: PerformanceThresholdRow[] = []
  Object.entries(thresholds as Record<string, unknown>).forEach(([metric, rules]) => {
    if (!rules || typeof rules !== 'object' || Array.isArray(rules)) return
    Object.entries(rules as Record<string, unknown>).forEach(([rule, result]) => {
      const ok = typeof result === 'boolean'
        ? !result
        : !!(
          result
          && typeof result === 'object'
          && !Array.isArray(result)
          && (result as { ok?: unknown }).ok === true
        )
      rows.push({ key: `${metric}:${rule}`, metric, rule, ok })
    })
  })
  return rows
}

export function getPerformanceThresholdGate(summary?: PerformanceSummary | null): PerformanceThresholdGate {
  const rows = getPerformanceThresholdRows(summary)
  const passed = rows.filter((row) => row.ok).length
  return {
    status: rows.length === 0 ? 'not_configured' : passed === rows.length ? 'passed' : 'failed',
    total: rows.length,
    passed,
    failed: rows.length - passed,
  }
}
