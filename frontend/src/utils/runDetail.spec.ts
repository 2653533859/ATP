import { describe, expect, it } from 'vitest'

import type { RunStepItem } from '@/api'
import {
  computeExpandedKeys,
  countScreenshotSteps,
  failedOrErrorSteps,
  healingTagColor,
  isParameterizedParent,
  normalizeFailureDiagnosis,
  normalizeRunHealing,
  primaryErrorText,
  readIterationStats,
  runStatusColor,
  summarizeStepStatuses,
  truncateText,
} from './runDetail'

function step(overrides: Partial<RunStepItem> = {}): RunStepItem {
  return {
    step_index: 0,
    name: 'step',
    status: 'passed',
    duration_ms: 10,
    request_data: null,
    response_data: null,
    error_message: null,
    screenshot_url: null,
    ...overrides,
  } as RunStepItem
}

describe('run detail helpers', () => {
  const steps = [
    step({ step_index: 0, status: 'passed', screenshot_url: 's0.png' }),
    step({ step_index: 1, status: 'failed', error_message: '断言失败' }),
    step({ step_index: 2, status: 'error', error_message: '连接超时' }),
    step({ step_index: 3, status: 'skipped' }),
  ]

  it('summarizes step statuses and derived collections', () => {
    expect(summarizeStepStatuses(steps)).toEqual({ passed: 1, failed: 1, error: 1, skipped: 1 })
    expect(failedOrErrorSteps(steps).map((s) => s.step_index)).toEqual([1, 2])
    expect(countScreenshotSteps(steps)).toBe(1)
  })

  it('expands failed steps, else the first step', () => {
    expect(computeExpandedKeys(steps)).toEqual([1, 2])
    expect(computeExpandedKeys([step({ step_index: 5, status: 'passed' })])).toEqual([5])
    expect(computeExpandedKeys([])).toEqual([])
  })

  it('reads parameterized iteration stats', () => {
    expect(isParameterizedParent({ iteration_total: 3 })).toBe(true)
    expect(isParameterizedParent({ iteration_total: 0 })).toBe(false)
    expect(isParameterizedParent(null)).toBe(false)
    expect(readIterationStats({ iteration_total: 5, iteration_passed: 3, iteration_failed: 1, iteration_error: 1 })).toEqual({
      total: 5,
      passed: 3,
      failed: 1,
      error: 1,
    })
    expect(readIterationStats(undefined)).toEqual({ total: 0, passed: 0, failed: 0, error: 0 })
  })

  it('maps status and healing colors', () => {
    expect(runStatusColor('failed')).toBe('red')
    expect(runStatusColor('mystery')).toBe('default')
    expect(healingTagColor('done')).toBe('green')
    expect(healingTagColor(null)).toBe('default')
  })

  it('normalizes run healing payloads', () => {
    expect(normalizeRunHealing(null)).toBeNull()
    expect(normalizeRunHealing({ suggestion: 'x' })).toBeNull()
    expect(normalizeRunHealing({ status: 'done', suggestion: '建议', at: '2026-07-10', cache_hit: 1 })).toEqual({
      status: 'done',
      suggestion: '建议',
      at: '2026-07-10',
      cache_hit: true,
    })
    expect(normalizeRunHealing({ status: 'pending', suggestion: 42 })).toEqual({
      status: 'pending',
      suggestion: null,
      at: null,
      cache_hit: false,
    })
  })

  it('normalizes failure diagnosis, rejecting incomplete payloads', () => {
    expect(normalizeFailureDiagnosis({ summary: 's' })).toBeNull()
    expect(
      normalizeFailureDiagnosis({
        status: 'done',
        source: 'llm',
        summary: '根因',
        failed_step_count: '2',
        repair_suggestions: [{ a: 1 }],
        error_samples: 'not-array',
      }),
    ).toEqual({
      status: 'done',
      source: 'llm',
      summary: '根因',
      at: '',
      failed_step_count: 2,
      screenshot_count: 0,
      repair_suggestions: [{ a: 1 }],
      error_samples: [],
    })
  })

  it('picks and truncates the primary error text', () => {
    expect(primaryErrorText(steps, null)).toBe('断言失败')
    expect(primaryErrorText([step({ status: 'passed' })], 'run 级错误')).toBe('run 级错误')
    expect(primaryErrorText([], null)).toBeNull()
    expect(primaryErrorText([step({ status: 'failed', error_message: 'x'.repeat(700) })], null)!.endsWith('...')).toBe(true)
    expect(truncateText('short')).toBe('short')
    expect(truncateText('y'.repeat(600), 500)).toHaveLength(503)
    expect(truncateText(null)).toBe('')
  })
})
