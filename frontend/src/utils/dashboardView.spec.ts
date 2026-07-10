import { describe, expect, it } from 'vitest'

import {
  cloneDefaultDashboardLayout,
  DEFAULT_DASHBOARD_LAYOUT,
  fillTrendGaps,
  generateDateRange,
  normalizeDashboardLayout,
} from './dashboardView'

describe('dashboard view helpers', () => {
  it('generates an inclusive daily date range', () => {
    expect(generateDateRange('2026-07-08', '2026-07-10')).toEqual(['2026-07-08', '2026-07-09', '2026-07-10'])
    expect(generateDateRange('2026-07-10', '2026-07-10')).toEqual(['2026-07-10'])
    expect(generateDateRange('2026-07-11', '2026-07-10')).toEqual([])
  })

  it('clones the default layout without shared references', () => {
    const clone = cloneDefaultDashboardLayout()
    expect(clone).toEqual(DEFAULT_DASHBOARD_LAYOUT)
    clone[0].visible = false
    expect(DEFAULT_DASHBOARD_LAYOUT[0].visible).toBe(true)
  })

  it('normalizes persisted layout: drops unknown, keeps order, appends absent defaults', () => {
    // duration_trend/pass_rate_trend 有效并保留顺序；unknown_chart 剔除；
    // 其余默认 key 完全缺席 → 追加到末尾（保持默认 visible）。
    const stored = [
      { key: 'duration_trend', visible: false },
      { key: 'unknown_chart', visible: true },
      { key: 'pass_rate_trend', visible: true },
    ]

    const result = normalizeDashboardLayout(stored)

    expect(result[0]).toEqual({ key: 'duration_trend', visible: false })
    expect(result[1]).toEqual({ key: 'pass_rate_trend', visible: true })
    expect(result.find((item) => (item.key as string) === 'unknown_chart')).toBeUndefined()
    for (const def of DEFAULT_DASHBOARD_LAYOUT) {
      expect(result.some((item) => item.key === def.key)).toBe(true)
    }
  })

  it('drops a malformed known key without re-appending it (present-but-invalid contract)', () => {
    // failure_top 缺 visible：既不保留也不补回（seenKeys 已含它）
    const result = normalizeDashboardLayout([{ key: 'failure_top' }, { key: 'pass_rate_trend', visible: true }])
    expect(result.some((item) => item.key === 'failure_top')).toBe(false)
    expect(result[0]).toEqual({ key: 'pass_rate_trend', visible: true })
  })

  it('falls back to default layout for non-array or fully invalid input', () => {
    expect(normalizeDashboardLayout(null)).toEqual(DEFAULT_DASHBOARD_LAYOUT)
    expect(normalizeDashboardLayout('bad')).toEqual(DEFAULT_DASHBOARD_LAYOUT)
    expect(normalizeDashboardLayout([{ key: 'nope', visible: true }])).toEqual(DEFAULT_DASHBOARD_LAYOUT)
  })

  it('fills daily trend gaps with zeros, honoring weekly and empty cases', () => {
    const today = new Date('2026-07-10T00:00:00Z')
    const data = [{ date: '2026-07-10', total: 4, passed: 3, rate: 75 }]
    const makeZero = (date: string) => ({ date, total: 0, passed: 0, rate: 0 })

    const filled = fillTrendGaps(data, 3, makeZero, { today })
    expect(filled.map((item) => item.date)).toEqual(['2026-07-08', '2026-07-09', '2026-07-10'])
    expect(filled[0]).toEqual({ date: '2026-07-08', total: 0, passed: 0, rate: 0 })
    expect(filled[2]).toEqual({ date: '2026-07-10', total: 4, passed: 3, rate: 75 })

    // weekly 不补零，原样返回
    expect(fillTrendGaps(data, 3, makeZero, { today, weekly: true })).toBe(data)
    // 空数据直接返回空
    expect(fillTrendGaps([], 3, makeZero, { today })).toEqual([])
  })
})
