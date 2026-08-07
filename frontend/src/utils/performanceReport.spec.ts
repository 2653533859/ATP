import { describe, expect, it } from 'vitest'
import { getPerformanceThresholdGate, getPerformanceThresholdRows } from './performanceReport'

describe('performanceReport', () => {
  it('normalizes threshold results and calculates the gate', () => {
    const summary = {
      thresholds: {
        http_req_duration: {
          'p(95)<500': { ok: true },
          'p(99)<800': { ok: false },
        },
        http_req_failed: {
          'rate<0.01': false,
        },
      },
    }

    expect(getPerformanceThresholdRows(summary)).toEqual([
      { key: 'http_req_duration:p(95)<500', metric: 'http_req_duration', rule: 'p(95)<500', ok: true },
      { key: 'http_req_duration:p(99)<800', metric: 'http_req_duration', rule: 'p(99)<800', ok: false },
      { key: 'http_req_failed:rate<0.01', metric: 'http_req_failed', rule: 'rate<0.01', ok: true },
    ])
    expect(getPerformanceThresholdGate(summary)).toEqual({ status: 'failed', total: 3, passed: 2, failed: 1 })
  })

  it('distinguishes a run without configured thresholds', () => {
    expect(getPerformanceThresholdGate({})).toEqual({
      status: 'not_configured',
      total: 0,
      passed: 0,
      failed: 0,
    })
  })
})
