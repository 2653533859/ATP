import { describe, expect, it } from 'vitest'

import { formatLocalDateTime } from './dateTime'

describe('formatLocalDateTime', () => {
  it('returns fallback for empty inputs', () => {
    expect(formatLocalDateTime(null)).toBe('-')
    expect(formatLocalDateTime(undefined, '—')).toBe('—')
    expect(formatLocalDateTime('   ')).toBe('-')
  })

  it('formats ISO UTC timestamps into browser local YYYY-MM-DD HH:mm:ss', () => {
    const sample = '2026-11-26T06:50:08Z'
    const d = new Date(sample)
    const pad = (n: number) => String(n).padStart(2, '0')
    const expected = `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())} ${pad(d.getHours())}:${pad(d.getMinutes())}:${pad(d.getSeconds())}`

    expect(formatLocalDateTime(sample)).toBe(expected)
    expect(formatLocalDateTime('2026-11-26T06:50:08')).toBe(expected)
  })
})
