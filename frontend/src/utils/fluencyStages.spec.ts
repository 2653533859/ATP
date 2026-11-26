import { describe, expect, it } from 'vitest'

import { parseFluencyStagesText, serializeFluencyStages } from './fluencyStages'

describe('fluencyStages helpers', () => {
  it('parses and serializes swipe and tap stages cleanly', () => {
    const source = JSON.stringify([
      { name: '上滑首页', action: 'swipe', coords: { x1: 540, y1: 1500, x2: 540, y2: 400 }, duration_seconds: 5 },
      { name: '点击详情', action: 'tap', coords: { x: 320, y: 800 }, duration_seconds: 3 },
    ])
    const parsed = parseFluencyStagesText(source)
    expect(parsed.valid).toBe(true)
    expect(parsed.rows).toHaveLength(2)
    expect(JSON.parse(serializeFluencyStages(parsed.rows))).toEqual([
      { name: '上滑首页', action: 'swipe', coords: { x1: 540, y1: 1500, x2: 540, y2: 400 }, duration_seconds: 5 },
      { name: '点击详情', action: 'tap', coords: { x: 320, y: 800 }, duration_seconds: 3 },
    ])
  })

  it('rejects malformed JSON cleanly', () => {
    expect(parseFluencyStagesText('{bad').valid).toBe(false)
    expect(parseFluencyStagesText('{}').valid).toBe(false)
    expect(serializeFluencyStages([])).toBe('')
  })
})
